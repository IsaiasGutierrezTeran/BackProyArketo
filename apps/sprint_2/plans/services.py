"""Business logic for plans (views only orchestrate)."""

from __future__ import annotations

from django.db.models import QuerySet

from core.exceptions import ApiException
from projects.models import Project
from projects.services import assert_can_edit_project, projects_for

from .models import Plan
from .validators import normalized_format


def plans_for(user) -> QuerySet[Plan]:
    """Plans belonging to projects the user can access."""
    return Plan.objects.filter(project__in=projects_for(user))


def _assert_can_use_project(user, project: Project) -> None:
    if not projects_for(user).filter(pk=project.pk).exists():
        # Don't reveal existence of projects the user can't access.
        raise ApiException(
            "Proyecto no encontrado.", code="not_found", status_code=404
        )
    # Viewers can see the project but not upload into it.
    assert_can_edit_project(user, project)


def create_plan(*, user, project: Project, file) -> Plan:
    """Validate edit rights and persist an uploaded plan."""
    _assert_can_use_project(user, project)
    return Plan.objects.create(
        project=project,
        uploaded_by=user,
        file=file,
        original_format=normalized_format(file.name),
        size_bytes=file.size,
    )
