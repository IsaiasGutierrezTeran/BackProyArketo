"""Detection jobs: one run of a detector over a plan, producing a 3D model."""

from __future__ import annotations

from django.db import models

from core.models import BaseModel


class JobStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    RUNNING = "running", "Ejecutando"
    COMPLETED = "completed", "Completado"
    FAILED = "failed", "Fallido"


class DetectionJob(BaseModel):
    plan = models.ForeignKey(
        "plans.Plan", on_delete=models.CASCADE, related_name="detection_jobs"
    )
    detector = models.CharField(max_length=20)  # mock | maskrcnn
    status = models.CharField(
        max_length=20, choices=JobStatus.choices, default=JobStatus.PENDING
    )
    # Normalized scene (walls/doors/windows/bounds) produced by the detector.
    raw_result = models.JSONField(null=True, blank=True)
    processing_ms = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    model3d = models.ForeignKey(
        "modeling.Model3D",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detection_job",
    )

    def __str__(self) -> str:
        return f"DetectionJob #{self.pk} ({self.detector}, {self.status})"
