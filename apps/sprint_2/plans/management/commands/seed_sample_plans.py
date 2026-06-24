"""Seed a sample plan + generated 3D model for each project that has none.

Lets a brand-new user explore the viewer/editor without uploading anything.
Uses the mock detector, so no GPU/weights/legacy service is required.

    python manage.py seed_sample_plans
"""

from __future__ import annotations

from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from detection.services import run_pipeline
from plans.models import Plan, PlanFormat
from projects.models import Project


def _sample_plan_png() -> bytes:
    """A minimal conventional floor plan: outer room split by one inner wall."""
    img = Image.new("RGB", (500, 400), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 450, 350], outline="black", width=4)
    draw.line([250, 50, 250, 350], fill="black", width=3)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class Command(BaseCommand):
    help = "Crea un plano de ejemplo + modelo 3D (mock) para proyectos sin planos."

    def handle(self, *args, **options):
        created = 0
        for project in Project.objects.all():
            if project.plans.exists():
                continue
            plan_bytes = _sample_plan_png()
            plan = Plan.objects.create(
                project=project,
                uploaded_by=project.owner,
                original_format=PlanFormat.PNG,
                size_bytes=len(plan_bytes),
            )
            plan.file.save(
                f"sample_project_{project.id}.png",
                ContentFile(plan_bytes),
                save=True,
            )
            run_pipeline(plan=plan, detector_name="mock")
            created += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  + plano + modelo 3D para '{project.name}'"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"seed_sample_plans: {created} generados.")
        )
