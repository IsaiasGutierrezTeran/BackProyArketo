"""Business logic for projects (views only orchestrate)."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from core.exceptions import ApiException

from .models import Comment, MembershipRole, Project, ProjectMembership, ProjectStatus

User = get_user_model()


def projects_for(user) -> QuerySet[Project]:
    """Projects visible to a user: owned + shared via membership. Superadmin: all."""
    qs = Project.objects.all()
    if getattr(user, "is_superadmin", False):
        return qs
    return qs.filter(Q(owner=user) | Q(memberships__user=user)).distinct()


def can_edit_project(user, project: Project) -> bool:
    """Owner, project editor, or superadmin may modify a project / its 3D model."""
    if getattr(user, "is_superadmin", False) or project.owner_id == user.id:
        return True
    return project.memberships.filter(
        user=user, role__in=[MembershipRole.OWNER, MembershipRole.EDITOR]
    ).exists()


def assert_can_edit_project(user, project: Project) -> Project:
    """Raise 403 unless the user may modify the project (write-gating for collaborators)."""
    if not can_edit_project(user, project):
        raise ApiException(
            "Solo lectura: no tienes permiso de edición en este proyecto.",
            code="forbidden", status_code=403,
        )
    return project


def create_project(*, owner, name: str, description: str = "", status: str | None = None,
                   thumbnail=None) -> Project:
    return Project.objects.create(
        owner=owner,
        name=name,
        description=description,
        status=status or ProjectStatus.DRAFT,
        thumbnail=thumbnail,
    )


def _owner_project(user, project_id: int) -> Project:
    """Return the project iff the user owns it (or is superadmin), else 404/403."""
    project = projects_for(user).filter(pk=project_id).first()
    if project is None:
        raise ApiException("Proyecto no encontrado.", code="not_found", status_code=404)
    if not (getattr(user, "is_superadmin", False) or project.owner_id == user.id):
        raise ApiException(
            "Solo el propietario puede gestionar colaboradores.",
            code="forbidden", status_code=403,
        )
    return project


def add_member(*, owner, project_id: int, email: str, role: str) -> ProjectMembership:
    """Invite a user (by email) to collaborate on a project (CU14)."""
    project = _owner_project(owner, project_id)
    member = User.objects.filter(email=email).first()
    if member is None:
        raise ApiException("Usuario no encontrado.", code="not_found", status_code=404)
    if member.id == project.owner_id:
        raise ApiException("El propietario ya tiene acceso total.", code="bad_request")
    membership, _ = ProjectMembership.objects.update_or_create(
        project=project, user=member, defaults={"role": role}
    )
    return membership


def remove_member(*, owner, project_id: int, membership_id: int) -> None:
    project = _owner_project(owner, project_id)
    ProjectMembership.objects.filter(pk=membership_id, project=project).delete()


def add_comment(*, user, project: Project, body: str, parent: Comment | None = None) -> Comment:
    return Comment.objects.create(project=project, author=user, body=body, parent=parent)


def dashboard_summary(user) -> dict:
    """Aggregate counts + recent projects for the user's dashboard (CU16)."""
    qs = projects_for(user)
    by_status = {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("id"))}
    recent = list(qs.order_by("-updated_at")[:5])
    return {
        "total": qs.count(),
        "by_status": {
            status.value: by_status.get(status.value, 0) for status in ProjectStatus
        },
        "recent": recent,
    }


def sync_changes(user, since: datetime | None = None) -> dict:
    """Incremental sync for offline/mobile clients (CU16).

    Returns the projects visible to the user that changed after ``since`` plus a
    ``server_time`` the client must persist and send back as ``since`` next time
    (delta sync). On the first sync (``since=None``) every visible project is
    returned.
    """
    server_time = timezone.now()
    qs = projects_for(user)
    if since is not None:
        qs = qs.filter(updated_at__gt=since)
    changed = list(qs.order_by("updated_at"))
    return {"server_time": server_time, "count": len(changed), "changed": changed}
