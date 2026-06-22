"""The Project aggregate root.

Everything in the system hangs off a Project: plans, 3D models, budgets,
versions and (Sprint 4) collaborators and comments.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class ProjectStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    ACTIVE = "active", "Activo"
    ARCHIVED = "archived", "Archivado"


class Project(BaseModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT
    )
    thumbnail = models.ImageField(upload_to="projects/thumbnails/", blank=True, null=True)

    class Meta(BaseModel.Meta):
        indexes = [models.Index(fields=["owner", "status"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.owner_id})"


class MembershipRole(models.TextChoices):
    """Collaboration roles within a single project (Sprint 4, CU14)."""

    OWNER = "owner", "Propietario"
    EDITOR = "editor", "Editor"
    VIEWER = "viewer", "Lector"


class MembershipStatus(models.TextChoices):
    """Invitation state of a collaboration (CU14).

    An invite stays PENDING until the invited user accepts it; only ACCEPTED
    memberships grant access to the project.
    """

    PENDING = "pending", "Pendiente"
    ACCEPTED = "accepted", "Aceptada"


class ProjectMembership(BaseModel):
    """A user's access (or pending invitation) to a shared project."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    role = models.CharField(
        max_length=12, choices=MembershipRole.choices, default=MembershipRole.VIEWER
    )
    status = models.CharField(
        max_length=10, choices=MembershipStatus.choices, default=MembershipStatus.ACCEPTED
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sent_invitations",
    )

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["project", "user"], name="uniq_project_member")
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.project_id} ({self.role}, {self.status})"


class Comment(BaseModel):
    """A comment on a project (optionally threaded)."""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="comments"
    )
    body = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )

    class Meta(BaseModel.Meta):
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment #{self.pk} on project {self.project_id}"
