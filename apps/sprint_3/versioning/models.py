"""Git-style project versions (snapshots)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class ProjectVersion(BaseModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="versions"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="project_versions",
    )
    version_number = models.PositiveIntegerField()
    message = models.TextField(blank=True)
    # Captured state: current models' geometry + budgets at commit time.
    snapshot = models.JSONField(default=dict)

    class Meta(BaseModel.Meta):
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "version_number"], name="uniq_project_version"
            )
        ]

    def __str__(self) -> str:
        return f"v{self.version_number} of project {self.project_id}"
