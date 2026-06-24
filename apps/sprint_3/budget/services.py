"""Business logic for budgets (views only orchestrate)."""

from __future__ import annotations

import math
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet

from core.exceptions import ApiException, Conflict
from projects.services import assert_can_edit_project, projects_for

from .models import Budget, BudgetItem, BudgetReview, BudgetStatus, Material


def budgets_for(user) -> QuerySet[Budget]:
    """Scope de presupuestos por rol (HU-12/HU-13).

    - superadmin: todos.
    - ingeniero (revisor): los de sus propios proyectos + cualquiera ya ENVIADO a
      revisión (no ve borradores ajenos).
    - cliente/arquitecto: solo los de los proyectos de los que es miembro.
    """
    qs = Budget.objects.prefetch_related("items", "review")
    if getattr(user, "is_superadmin", False):
        return qs
    own = Q(project__in=projects_for(user))
    if getattr(user, "is_ingeniero", False):
        return qs.filter(own | ~Q(status=BudgetStatus.DRAFT))
    return qs.filter(own)


def _assert_project_access(user, project_id: int):
    project = projects_for(user).filter(pk=project_id).first()
    if project is None:
        raise ApiException(
            "Proyecto no encontrado.", code="not_found", status_code=404
        )
    return assert_can_edit_project(user, project)


@transaction.atomic
def create_budget(
    *,
    user,
    project_id: int,
    items: list[dict],
    labor_people: int = 0,
    labor_cost: Decimal | None = None,
    currency: str | None = None,
) -> Budget:
    """Create a budget, snapshotting prices and computing subtotals/total (CU12)."""
    project = _assert_project_access(user, project_id)
    labor_cost = Decimal(labor_cost or 0)

    budget = Budget.objects.create(
        project=project,
        created_by=user,
        labor_people=labor_people,
        labor_cost=labor_cost,
        currency=currency or settings.DEFAULT_CURRENCY,
        status=BudgetStatus.DRAFT,
    )

    materials_cost = Decimal("0")
    rows: list[BudgetItem] = []
    for item in items:
        material = Material.objects.filter(
            pk=item["material"], is_active=True
        ).first()
        if material is None:
            raise ApiException(
                f"Material {item['material']} no existe o está inactivo.",
                code="bad_request",
            )
        quantity = Decimal(item["quantity"])
        subtotal = (quantity * material.unit_price).quantize(Decimal("0.01"))
        materials_cost += subtotal
        rows.append(
            BudgetItem(
                budget=budget,
                material=material,
                quantity=quantity,
                unit_price_snapshot=material.unit_price,
                subtotal=subtotal,
            )
        )
    BudgetItem.objects.bulk_create(rows)

    budget.materials_cost = materials_cost
    budget.total = materials_cost + labor_cost
    budget.save(update_fields=["materials_cost", "total", "updated_at"])
    return budget


def submit_budget(*, user, budget: Budget) -> Budget:
    # Solo el autor/editor del proyecto puede enviar a revisión (no el revisor).
    _assert_project_access(user, budget.project_id)
    if budget.status not in {BudgetStatus.DRAFT, BudgetStatus.OBSERVED}:
        raise Conflict(
            "Solo se puede enviar un presupuesto en borrador u observado."
        )
    budget.status = BudgetStatus.SUBMITTED
    budget.save(update_fields=["status", "updated_at"])
    return budget


def delete_budget(*, user, budget: Budget) -> None:
    """Borra un presupuesto: solo autor/editor del proyecto y si no está aprobado."""
    _assert_project_access(user, budget.project_id)
    if budget.status == BudgetStatus.APPROVED:
        raise Conflict("No se puede eliminar un presupuesto aprobado.")
    budget.delete()


_DECISION_TO_STATUS = {
    "approved": BudgetStatus.APPROVED,
    "observed": BudgetStatus.OBSERVED,
    "rejected": BudgetStatus.REJECTED,
}


@transaction.atomic
def review_budget(
    *, budget: Budget, reviewer, decision: str, comments: str = ""
) -> Budget:
    """Engineer review: approve, observe or reject a submitted budget (CU13).

    - approved → APPROVED (terminal OK)
    - observed → OBSERVED (devuelto al autor; puede reenviarse tras corregir)
    - rejected → REJECTED (terminal; no puede reenviarse)
    """
    if not (
        getattr(reviewer, "is_ingeniero", False)
        or getattr(reviewer, "is_superadmin", False)
    ):
        raise ApiException(
            "Solo el rol Ingeniero puede revisar presupuestos.",
            code="forbidden",
            status_code=403,
        )
    if budget.status != BudgetStatus.SUBMITTED:
        raise Conflict("El presupuesto debe estar 'enviado' para revisarse.")

    BudgetReview.objects.update_or_create(
        budget=budget,
        defaults={
            "reviewer": reviewer,
            "decision": decision,
            "comments": comments,
        },
    )
    budget.status = _DECISION_TO_STATUS.get(decision, BudgetStatus.OBSERVED)
    budget.save(update_fields=["status", "updated_at"])
    return budget


# --- Estimación automática de materiales desde el modelo 3D (cómputo métrico) ---
# Ratios aproximados para vivienda de ladrillo (Bolivia). EDITABLES: ajusta aquí.
_R_LADRILLO_M2 = 33.0  # unidades de ladrillo por m² de muro
_R_CEMENTO_MURO = Decimal("0.35")  # bolsa por m² de muro (asiento + revoque)
_R_CEMENTO_PISO = Decimal("0.20")  # bolsa por m² de piso (contrapiso)
_R_ARENA_MURO = Decimal("0.04")  # m³ por m² de muro
_R_ARENA_PISO = Decimal("0.03")  # m³ por m² de piso
_R_GRAVA_PISO = Decimal("0.04")  # m³ por m² de piso
_R_FIERRO_PISO = Decimal(
    "0.7"
)  # varillas 1/2" por m² (estimación estructural gruesa)
_R_CERAMICA = Decimal("1.05")  # m² de cerámica por m² de piso (5% desperdicio)
_R_PINTURA_GAL = Decimal(
    "0.05"
)  # galón por m² de muro (~0.2 L/m² ÷ 3.785 L/galón)


def _find_material(*needles, unit: str | None = None) -> Material | None:
    """Primer material activo cuyo nombre contenga alguno de los `needles` (en orden)."""
    base = Material.objects.filter(is_active=True)
    if unit:
        base = base.filter(unit=unit)
    for needle in needles:
        mat = (
            base.filter(name__icontains=needle).order_by("unit_price").first()
        )
        if mat is not None:
            return mat
    return None


def estimate_items_from_model(model3d) -> tuple[list[dict], dict]:
    """Cómputo métrico: a partir de la geometría del modelo devuelve
    (items=[{material, quantity}], resumen). No persiste nada."""
    scene = model3d.scene_json or {}
    walls = scene.get("walls") or []

    pts: list[tuple[float, float]] = []
    wall_area = 0.0
    for w in walls:
        s_, e_ = w.get("start") or {}, w.get("end") or {}
        sx, sy = float(s_.get("x", 0.0)), float(s_.get("y", 0.0))
        ex, ey = float(e_.get("x", 0.0)), float(e_.get("y", 0.0))
        pts += [(sx, sy), (ex, ey)]
        wall_area += math.hypot(ex - sx, ey - sy) * float(
            w.get("height") or 2.7
        )

    fw = fd = 0.0
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        fw, fd = max(xs) - min(xs), max(ys) - min(ys)

    # Si la escena viene normalizada (lados < 2.5 m), escalar a tamaño real.
    longest = max(fw, fd)
    scaled = False
    if 0 < longest < 2.5:
        k = 14.0 / longest
        fw, fd, wall_area, scaled = fw * k, fd * k, wall_area * (k * k), True

    floor_area = fw * fd
    n_doors = len(scene.get("doors") or [])
    n_windows = len(scene.get("windows") or [])

    wa = Decimal(str(wall_area))
    fa = Decimal(str(floor_area))

    plan = [
        (
            _find_material(
                "Ladrillo 6 huecos", "Ladrillo gambote", "Ladrillo"
            ),
            Decimal(str(wall_area * _R_LADRILLO_M2)),
        ),
        (
            _find_material(
                "Cemento Portland IP-30", "Cemento Portland", "Cemento"
            ),
            wa * _R_CEMENTO_MURO + fa * _R_CEMENTO_PISO,
        ),
        (
            _find_material("Arena común", "Arena", unit="m³"),
            wa * _R_ARENA_MURO + fa * _R_ARENA_PISO,
        ),
        (_find_material("Grava", unit="m³"), fa * _R_GRAVA_PISO),
        (
            _find_material(
                "Fierro corrugado 1/2", "Fierro corrugado 3/8", "Fierro"
            ),
            fa * _R_FIERRO_PISO,
        ),
        (
            _find_material("Cerámica", "Piso cerámico", "Porcelanato"),
            fa * _R_CERAMICA,
        ),
        (_find_material("Látex", "Pintura"), wa * _R_PINTURA_GAL),
        (_find_material("Puerta"), Decimal(n_doors)),
        (_find_material("Ventana"), Decimal(n_windows)),
    ]

    items: list[dict] = []
    for mat, qty in plan:
        if mat is None:
            continue
        q = Decimal(str(qty)).quantize(Decimal("0.01"))
        if q <= 0:
            continue
        items.append({"material": mat.id, "quantity": q})

    summary = {
        "wall_area_m2": round(float(wa), 2),
        "floor_area_m2": round(float(fa), 2),
        "footprint_m": [round(fw, 2), round(fd, 2)],
        "doors": n_doors,
        "windows": n_windows,
        "scaled": scaled,
    }
    return items, summary


def estimate_budget(
    *, user, model3d_id: int, currency: str | None = None
) -> Budget:
    """Crea un presupuesto BORRADOR estimado desde la geometría del modelo 3D."""
    from modeling.models import (
        Model3D,
    )  # import perezoso (evita ciclos de carga)

    model = Model3D.objects.filter(
        pk=model3d_id, project__in=projects_for(user)
    ).first()
    if model is None:
        raise ApiException(
            "Modelo 3D no encontrado.", code="not_found", status_code=404
        )
    items, _summary = estimate_items_from_model(model)
    if not items:
        raise ApiException(
            "No se pudo estimar materiales (el modelo no tiene geometría suficiente).",
            code="bad_request",
        )
    return create_budget(
        user=user,
        project_id=model.project_id,
        items=items,
        labor_people=0,
        labor_cost=None,
        currency=currency,
    )
