"""Structural risk analyses and findings for a 3D model."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class AnalysisStatus(models.TextChoices):
    COMPLETED = "completed", "Completado"
    FAILED = "failed", "Fallido"


class Severity(models.TextChoices):
    LOW = "low", "Baja"
    MEDIUM = "medium", "Media"
    HIGH = "high", "Alta"
    CRITICAL = "critical", "Crítica"


class RiskAnalysis(BaseModel):
    model3d = models.ForeignKey(
        "modeling.Model3D", on_delete=models.CASCADE, related_name="risk_analyses"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="risk_analyses",
    )
    provider = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=12, choices=AnalysisStatus.choices, default=AnalysisStatus.COMPLETED
    )
    summary = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"RiskAnalysis #{self.pk} (model {self.model3d_id})"


class RiskFinding(BaseModel):
    analysis = models.ForeignKey(
        RiskAnalysis, on_delete=models.CASCADE, related_name="findings"
    )
    category = models.CharField(max_length=60)
    severity = models.CharField(max_length=12, choices=Severity.choices)
    description = models.TextField()
    suggestion = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["-severity", "-created_at"]

    def __str__(self) -> str:
        return f"{self.severity}: {self.category}"
