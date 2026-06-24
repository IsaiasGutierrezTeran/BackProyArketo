"""Generated 3D models (.glb) and their editable scene geometry."""

from __future__ import annotations

from django.db import models

from core.models import BaseModel


class Model3D(BaseModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="models3d"
    )
    source_plan = models.ForeignKey(
        "plans.Plan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="models3d",
    )
    glb_file = models.FileField(upload_to="models3d/")
    # Editable geometry (walls/doors/windows) — the source of truth for re-export.
    scene_json = models.JSONField(null=True, blank=True)
    bounds = models.JSONField(null=True, blank=True)
    element_count = models.PositiveIntegerField(default=0)
    model_name = models.CharField(max_length=60, blank=True)
    unit = models.CharField(max_length=20, default="meters")
    is_current = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=["project", "is_current"])]

    def __str__(self) -> str:
        return f"Model3D #{self.pk} (project {self.project_id})"
