"""Business logic for budgets (views only orchestrate)."""

from __future__ import annotations

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
        raise ApiException("Proyecto no encontrado.", code="not_found", status_code=404)
    return assert_can_edit_project(user, project)


@transaction.atomic
def create_budget(*, user, project_id: int, items: list[dict],
                  labor_people: int = 0, labor_cost: Decimal | None = None,
                  currency: str | None = None) -> Budget:
    """Create a budget, snapshotting prices and computing subtotals/total (CU12)."""
    project = _assert_project_access(user, project_id)
    labor_cost = Decimal(labor_cost or 0)

    budget = Budget.objects.create(
        project=project, created_by=user, labor_people=labor_people,
        labor_cost=labor_cost, currency=currency or settings.DEFAULT_CURRENCY,
        status=BudgetStatus.DRAFT,
    )

    materials_cost = Decimal("0")
    rows: list[BudgetItem] = []
    for item in items:
        material = Material.objects.filter(pk=item["material"], is_active=True).first()
        if material is None:
            raise ApiException(
                f"Material {item['material']} no existe o está inactivo.",
                code="bad_request",
            )
        quantity = Decimal(item["quantity"])
        subtotal = (quantity * material.unit_price).quantize(Decimal("0.01"))
        materials_cost += subtotal
        rows.append(BudgetItem(
            budget=budget, material=material, quantity=quantity,
            unit_price_snapshot=material.unit_price, subtotal=subtotal,
        ))
    BudgetItem.objects.bulk_create(rows)

    budget.materials_cost = materials_cost
    budget.total = materials_cost + labor_cost
    budget.save(update_fields=["materials_cost", "total", "updated_at"])
    return budget


def submit_budget(*, user, budget: Budget) -> Budget:
    # Solo el autor/editor del proyecto puede enviar a revisión (no el revisor).
    _assert_project_access(user, budget.project_id)
    if budget.status not in {BudgetStatus.DRAFT, BudgetStatus.OBSERVED}:
        raise Conflict("Solo se puede enviar un presupuesto en borrador u observado.")
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
def review_budget(*, budget: Budget, reviewer, decision: str, comments: str = "") -> Budget:
    """Engineer review: approve, observe or reject a submitted budget (CU13).

    - approved → APPROVED (terminal OK)
    - observed → OBSERVED (devuelto al autor; puede reenviarse tras corregir)
    - rejected → REJECTED (terminal; no puede reenviarse)
    """
    if not (getattr(reviewer, "is_ingeniero", False) or getattr(reviewer, "is_superadmin", False)):
        raise ApiException(
            "Solo el rol Ingeniero puede revisar presupuestos.",
            code="forbidden", status_code=403,
        )
    if budget.status != BudgetStatus.SUBMITTED:
        raise Conflict("El presupuesto debe estar 'enviado' para revisarse.")

    BudgetReview.objects.update_or_create(
        budget=budget,
        defaults={"reviewer": reviewer, "decision": decision, "comments": comments},
    )
    budget.status = _DECISION_TO_STATUS.get(decision, BudgetStatus.OBSERVED)
    budget.save(update_fields=["status", "updated_at"])
    return budget
