"""Uploaded 2D floor-plan source files (CU4)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class PlanFormat(models.TextChoices):
    PDF = "pdf", "PDF"
    JPG = "jpg", "JPG"
    PNG = "png", "PNG"
    CSV = "csv", "CSV"


class PlanStatus(models.TextChoices):
    UPLOADED = "uploaded", "Subido"
    PROCESSING = "processing", "Procesando"
    PROCESSED = "processed", "Procesado"
    FAILED = "failed", "Fallido"


class Plan(BaseModel):
    """A 2D plan file belonging to a project. Detection turns it into a 3D model."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="plans"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="uploaded_plans",
    )
    file = models.FileField(upload_to="plans/")
    original_format = models.CharField(max_length=8, choices=PlanFormat.choices)
    size_bytes = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=PlanStatus.choices, default=PlanStatus.UPLOADED
    )

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=["project", "status"])]

    def __str__(self) -> str:
        return f"Plan #{self.pk} ({self.original_format}) of project {self.project_id}"

    @property
    def is_image(self) -> bool:
        return self.original_format in {PlanFormat.JPG, PlanFormat.PNG}
