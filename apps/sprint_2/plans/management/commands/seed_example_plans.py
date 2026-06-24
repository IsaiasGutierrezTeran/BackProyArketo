"""Seed example floor plans (CU4 + CU5).

If `BACKEND/seed_assets/plans/` contains images, each one becomes a plan. If the
folder is empty, three realistic synthetic floor plans are rendered instead.
Each plan gets a 3D model via the mock detector. Idempotent.

    python manage.py seed_example_plans
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from accounts.models import Role
from detection.services import run_pipeline
from plans.models import Plan, PlanFormat
from projects.models import Project, ProjectStatus

User = get_user_model()

WALL = (28, 32, 40)
ROOM_FILL = (226, 238, 248)
CAR = (203, 209, 218)
CAR_GLASS = (168, 180, 198)
TEXT = (44, 52, 66)

# (x1, y1, x2, y2, label, cars)  — cars > 0 marks a garage.
PLAN_SPECS = [
    (
        "Casa con garaje doble (~150 m²)",
        [
            (60, 60, 360, 300, "33,1 m²", 0),
            (360, 60, 500, 300, "15,6 m²", 0),
            (500, 60, 690, 230, "16,7 m²", 0),
            (690, 110, 840, 230, "8,5 m²", 0),
            (500, 230, 610, 330, "4 m²", 0),
            (60, 420, 250, 620, "11,5 m²", 0),
            (250, 470, 430, 620, "5,3 m²", 0),
            (560, 320, 840, 620, "39,4 m²", 2),
        ],
    ),
    (
        "Vivienda amplia (~220 m²)",
        [
            (60, 60, 300, 300, "18 m²", 0),
            (300, 60, 540, 300, "22,5 m²", 0),
            (560, 60, 840, 360, "51,9 m²", 0),
            (60, 320, 360, 620, "34,1 m²", 2),
            (380, 320, 540, 620, "17,1 m²", 0),
            (560, 380, 840, 620, "13,8 m²", 0),
        ],
    ),
    (
        "Casa de campo (~175 m²)",
        [
            (60, 60, 280, 260, "16,3 m²", 0),
            (300, 60, 520, 260, "13,6 m²", 0),
            (540, 60, 840, 360, "35,9 m²", 0),
            (60, 280, 280, 460, "15,9 m²", 0),
            (60, 480, 300, 620, "18,6 m²", 1),
            (320, 300, 520, 620, "12,7 m²", 0),
            (540, 380, 840, 620, "13,1 m²", 0),
        ],
    ),
]


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _car(d: ImageDraw.ImageDraw, box) -> None:
    x1, y1, x2, y2 = box
    d.rounded_rectangle(
        [x1, y1, x2, y2], radius=16, fill=CAR, outline=(120, 126, 138), width=2
    )
    h = y2 - y1
    d.rounded_rectangle(
        [x1 + 8, y1 + h * 0.18, x2 - 8, y1 + h * 0.42],
        radius=8,
        fill=CAR_GLASS,
    )
    d.rounded_rectangle(
        [x1 + 8, y1 + h * 0.56, x2 - 8, y1 + h * 0.80],
        radius=8,
        fill=CAR_GLASS,
    )


def render_plan(rooms, w: int = 900, h: int = 680) -> bytes:
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, w - 40, h - 40], outline=WALL, width=9)
    font = _font(22)
    for x1, y1, x2, y2, label, cars in rooms:
        d.rectangle([x1, y1, x2, y2], fill=ROOM_FILL, outline=WALL, width=4)
        if cars:
            slot = (x2 - x1) / cars
            for i in range(cars):
                cx1 = x1 + slot * i + slot * 0.18
                cx2 = x1 + slot * (i + 1) - slot * 0.18
                _car(d, (cx1, y1 + 30, cx2, y2 - 30))
        tb = d.textbbox((0, 0), label, font=font)
        d.text(
            (
                (x1 + x2) / 2 - (tb[2] - tb[0]) / 2,
                (y1 + y2) / 2 - (tb[3] - tb[1]) / 2,
            ),
            label,
            fill=TEXT,
            font=font,
        )
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Command(BaseCommand):
    help = "Crea un proyecto con planos de ejemplo (reales si los pones en seed_assets/plans, o sintéticos)."

    def handle(self, *args, **options):
        owner = (
            User.objects.filter(email="cliente@arketo.dev").first()
            or User.objects.filter(role=Role.CLIENTE).first()
            or User.objects.first()
        )
        if owner is None:
            self.stdout.write(
                self.style.WARNING(
                    "No hay usuarios; corre seed_users primero."
                )
            )
            return

        project, _ = Project.objects.get_or_create(
            owner=owner,
            name="Planos de ejemplo",
            defaults={
                "status": ProjectStatus.ACTIVE,
                "description": "Planos de muestra para explorar la conversión 2D→3D.",
            },
        )

        sources = self._real_images()
        expected = len(sources) if sources else len(PLAN_SPECS)
        if project.plans.count() >= expected:
            self.stdout.write(
                self.style.SUCCESS("seed_example_plans: ya estaba sembrado.")
            )
            return

        created = 0
        if sources:
            for path in sources:
                self._add_plan(
                    project,
                    owner,
                    path.read_bytes(),
                    path.suffix.lstrip(".").lower(),
                    path.name,
                )
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  + (real) {path.name}")
                )
        else:
            for name, rooms in PLAN_SPECS:
                self._add_plan(project, owner, render_plan(rooms), "png", name)
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_example_plans: {created} planos + modelos 3D en el proyecto '{project.name}'."
            )
        )

    def _real_images(self) -> list[Path]:
        folder = Path(settings.BASE_DIR) / "seed_assets" / "plans"
        if not folder.exists():
            return []
        return sorted(
            p
            for p in folder.iterdir()
            if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )

    def _add_plan(
        self, project, owner, data: bytes, ext: str, label: str
    ) -> None:
        fmt = PlanFormat.JPG if ext in {"jpg", "jpeg"} else PlanFormat.PNG
        plan = Plan.objects.create(
            project=project,
            uploaded_by=owner,
            original_format=fmt,
            size_bytes=len(data),
        )
        safe = "".join(c if c.isalnum() else "_" for c in label)[:40]
        plan.file.save(
            f"example_{project.id}_{safe}.{ 'jpg' if fmt == PlanFormat.JPG else 'png' }",
            ContentFile(data),
            save=True,
        )
        run_pipeline(plan=plan, detector_name="mock")
