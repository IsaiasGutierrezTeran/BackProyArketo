"""Master demo seeder — populates almost the whole system for testing.

Creates users (all roles), projects, plans + generated 3D models (mock detector),
itemized **budgets with Bolivian prices (Bs)**, risk analyses, collaborators,
comments, versions and subscriptions. Idempotent.

    python manage.py seed_demo

Runs the base seeders first (users, materials, subscription plans), then layers
the rich demo data on top.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from accounts.models import Role
from billing.services import subscribe
from budget.models import Material
from budget.services import create_budget, review_budget, submit_budget
from detection.services import run_pipeline
from plans.models import Plan, PlanFormat
from projects.models import (
    MembershipRole,
    Project,
    ProjectMembership,
    ProjectStatus,
)
from projects.services import add_comment, add_member
from risk.services import analyze_model
from versioning.services import commit_version

User = get_user_model()
PWD = "Demo12345"

# Extra users (besides the 4 from seed_users). (email, full_name, role)
EXTRA_USERS = [
    ("maria@arketo.dev", "María Quispe", Role.CLIENTE),
    ("jose@arketo.dev", "José Mamani", Role.CLIENTE),
    ("ana@arketo.dev", "Ana Vargas", Role.CLIENTE),
    ("luis@arketo.dev", "Luis Choque", Role.CLIENTE),
    ("carla@arketo.dev", "Carla Rojas", Role.ARQUITECTO),
    ("pedro@arketo.dev", "Pedro Flores", Role.ARQUITECTO),
    ("sofia@arketo.dev", "Sofía Gutiérrez", Role.INGENIERO),
]

# Projects inspired by real single-story house plans. (name, area_m2, status)
PROJECTS = [
    ("Casa Roble — 150 m²", 150, ProjectStatus.ACTIVE),
    ("Casa Cedro — 220 m²", 220, ProjectStatus.ACTIVE),
    ("Casa Aliso — 175 m²", 175, ProjectStatus.ACTIVE),
    ("Vivienda Las Lomas", 130, ProjectStatus.DRAFT),
    ("Residencial El Mirador", 245, ProjectStatus.ACTIVE),
    ("Casa de Campo Tarija", 165, ProjectStatus.ACTIVE),
    ("Dúplex Equipetrol", 190, ProjectStatus.DRAFT),
    ("Casa Jardín Sur", 140, ProjectStatus.ACTIVE),
    ("Chalet Los Pinos", 210, ProjectStatus.ACTIVE),
    ("Vivienda Económica VIS", 72, ProjectStatus.ACTIVE),
    ("Casa Patio Central", 158, ProjectStatus.ARCHIVED),
    ("Residencia Achumani", 280, ProjectStatus.ACTIVE),
]

# Material basket per built m² (material name -> quantity per m²).
BASKET = [
    ("Cemento Portland IP-30 (bolsa 50 kg)", 1.2),
    ("Ladrillo gambote 6 huecos", 55),
    ("Arena fina", 0.08),
    ("Grava / ripio", 0.06),
    ('Fierro corrugado 1/2" (varilla 12 m)', 0.5),
    ("Cerámica de piso (alta)", 0.9),
    ("Pintura látex (balde 4 L)", 0.15),
    ("Calamina galvanizada N°28 (plancha)", 0.2),
]


def _plan_png(area: int) -> bytes:
    """A simple floor-plan-like image (outer walls + a couple inner walls)."""
    img = Image.new("RGB", (560, 420), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 520, 380], outline="black", width=6)
    d.line([300, 40, 300, 380], fill="black", width=5)
    d.line([40, 220, 300, 220], fill="black", width=5)
    if area > 180:
        d.line([300, 210, 520, 210], fill="black", width=5)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Command(BaseCommand):
    help = (
        "Puebla casi todo el sistema con datos demo realistas (idempotente)."
    )

    def handle(self, *args, **options):
        call_command("seed_users")
        call_command("seed_materials")
        call_command("seed_plans")

        users = self._ensure_users()
        clientes = [u for u in users if u.role == Role.CLIENTE]
        arquitectos = [u for u in users if u.role == Role.ARQUITECTO]
        engineer = User.objects.filter(role=Role.INGENIERO).first()
        materials = {m.name: m for m in Material.objects.all()}

        owners = clientes + arquitectos
        created = 0
        for i, (name, area, status) in enumerate(PROJECTS):
            owner = owners[i % len(owners)]
            if Project.objects.filter(owner=owner, name=name).exists():
                continue
            self._build_project(
                i, name, area, status, owner, arquitectos, engineer, materials
            )
            created += 1
            self.stdout.write(
                self.style.SUCCESS(f"  + {name} ({owner.email})")
            )

        self._subscriptions(clientes, arquitectos)
        self._summary(created)

    # ------------------------------------------------------------------ users
    def _ensure_users(self) -> list:
        for email, full_name, role in EXTRA_USERS:
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(
                    email=email, password=PWD, full_name=full_name, role=role
                )
        return list(User.objects.all())

    # --------------------------------------------------------------- projects
    def _build_project(
        self, i, name, area, status, owner, arquitectos, engineer, materials
    ):
        project = Project.objects.create(
            owner=owner,
            name=name,
            status=status,
            description=f"Vivienda de {area} m² construidos. Datos de demostración.",
        )

        # Plan + 3D model (mock detector)
        png = _plan_png(area)
        plan = Plan.objects.create(
            project=project,
            uploaded_by=owner,
            original_format=PlanFormat.PNG,
            size_bytes=len(png),
        )
        plan.file.save(
            f"demo_plan_{project.id}.png", ContentFile(png), save=True
        )
        job = run_pipeline(plan=plan, detector_name="mock")
        model = job.model3d

        # Budget with Bolivian prices
        items = [
            {"material": materials[n].id, "quantity": f"{area * q:.2f}"}
            for n, q in BASKET
            if n in materials
        ]
        if items:
            budget = create_budget(
                user=owner,
                project_id=project.id,
                items=items,
                labor_people=max(4, area // 25),
                labor_cost=Decimal(area) * Decimal("350"),
                currency="Bs",
            )
            # Vary the workflow: draft / submitted / reviewed.
            phase = i % 3
            if phase >= 1:
                submit_budget(user=owner, budget=budget)
            if phase == 2 and engineer:
                decision = "approved" if i % 2 == 0 else "observed"
                review_budget(
                    budget=budget,
                    reviewer=engineer,
                    decision=decision,
                    comments=(
                        "Revisado por ingeniería estructural."
                        if decision == "approved"
                        else "Revisar cuantía de acero en vigas."
                    ),
                )

        # Risk analysis on the generated model
        if model:
            analyze_model(user=owner, model3d=model)

        # Collaboration: invite an architect as editor (when owner isn't one)
        if owner.role == Role.CLIENTE and arquitectos:
            collaborator = arquitectos[i % len(arquitectos)]
            if collaborator.id != owner.id:
                add_member(
                    owner=owner,
                    project_id=project.id,
                    email=collaborator.email,
                    role=MembershipRole.EDITOR,
                )

        # A couple of comments
        add_comment(
            user=owner,
            project=project,
            body="Subí el plano inicial, revisemos el presupuesto.",
        )

        # A saved version for some projects
        if i % 2 == 0:
            commit_version(
                user=owner,
                project_id=project.id,
                message="Versión inicial del proyecto",
            )

    # ----------------------------------------------------------- subscriptions
    def _subscriptions(self, clientes, arquitectos):
        targets = [(clientes[0], "pro")] if clientes else []
        if len(clientes) > 1:
            targets.append((clientes[1], "enterprise"))
        if arquitectos:
            targets.append((arquitectos[0], "pro"))
        for user, plan in targets:
            try:
                subscribe(user=user, plan_code=plan)
            except Exception:
                pass

    # ----------------------------------------------------------------- report
    def _summary(self, created):
        from billing.models import Subscription
        from budget.models import Budget
        from modeling.models import Model3D
        from risk.models import RiskAnalysis

        self.stdout.write(
            self.style.SUCCESS(
                "\nseed_demo listo:"
                f"\n  usuarios:       {User.objects.count()}"
                f"\n  proyectos:      {Project.objects.count()} (+{created} nuevos)"
                f"\n  planos:         {Plan.objects.count()}"
                f"\n  modelos 3D:     {Model3D.objects.count()}"
                f"\n  presupuestos:   {Budget.objects.count()}"
                f"\n  análisis riesgo:{RiskAnalysis.objects.count()}"
                f"\n  suscripciones:  {Subscription.objects.count()}"
                f"\n  materiales:     {Material.objects.count()}"
            )
        )
