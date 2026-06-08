"""Business logic for project versioning (CU15)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Max, QuerySet

from core.exceptions import ApiException
from modeling.models import Model3D
from modeling.services import replace_scene
from projects.services import assert_can_edit_project, projects_for

from .models import ProjectVersion


def versions_for(user) -> QuerySet[ProjectVersion]:
    return ProjectVersion.objects.filter(project__in=projects_for(user))


def _snapshot(project) -> dict:
    """Capture the current 3D geometry and budget headers of a project."""
    models = [
        {"id": m.id, "scene_json": m.scene_json, "is_current": m.is_current}
        for m in project.models3d.all()
    ]
    budgets = [
        {"id": b.id, "total": str(b.total), "status": b.status}
        for b in project.budgets.all()
    ]
    return {"models": models, "budgets": budgets}


@transaction.atomic
def commit_version(*, user, project_id: int, message: str) -> ProjectVersion:
    """Save a new version (commit) of the project's current state."""
    project = projects_for(user).filter(pk=project_id).first()
    if project is None:
        raise ApiException("Proyecto no encontrado.", code="not_found", status_code=404)
    assert_can_edit_project(user, project)
    next_number = (project.versions.aggregate(m=Max("version_number"))["m"] or 0) + 1
    return ProjectVersion.objects.create(
        project=project, author=user, version_number=next_number,
        message=message, snapshot=_snapshot(project),
    )


@transaction.atomic
def restore_version(*, user, version: ProjectVersion) -> ProjectVersion:
    """Restore each model's geometry from the snapshot and regenerate its GLB."""
    assert_can_edit_project(user, version.project)
    for entry in (version.snapshot or {}).get("models", []):
        model = Model3D.objects.filter(pk=entry["id"], project=version.project).first()
        if model is not None and entry.get("scene_json"):
            replace_scene(model=model, scene_json=entry["scene_json"])
    return version


def _scene_counts(scene_json: dict | None) -> dict:
    sj = scene_json or {}
    return {k: len(sj.get(k) or []) for k in ("walls", "doors", "windows")}


def diff_versions(*, base: ProjectVersion, target: ProjectVersion) -> dict:
    """Compare two versions of the same project (Git-style diff, CU15).

    Reports, per 3D model and per budget, whether it was added / removed /
    modified / unchanged between ``base`` and ``target``, plus element counts.
    """
    base_models = {m["id"]: m for m in (base.snapshot or {}).get("models", [])}
    target_models = {m["id"]: m for m in (target.snapshot or {}).get("models", [])}
    model_diffs = []
    for mid in sorted(set(base_models) | set(target_models)):
        b, t = base_models.get(mid), target_models.get(mid)
        if b is None:
            change = "added"
        elif t is None:
            change = "removed"
        elif b.get("scene_json") != t.get("scene_json"):
            change = "modified"
        else:
            change = "unchanged"
        model_diffs.append({
            "model_id": mid,
            "change": change,
            "from_counts": _scene_counts(b.get("scene_json")) if b else None,
            "to_counts": _scene_counts(t.get("scene_json")) if t else None,
        })

    base_budgets = {x["id"]: x for x in (base.snapshot or {}).get("budgets", [])}
    target_budgets = {x["id"]: x for x in (target.snapshot or {}).get("budgets", [])}
    budget_diffs = []
    for bid in sorted(set(base_budgets) | set(target_budgets)):
        b, t = base_budgets.get(bid), target_budgets.get(bid)
        if b is None:
            change = "added"
        elif t is None:
            change = "removed"
        elif b != t:
            change = "modified"
        else:
            change = "unchanged"
        budget_diffs.append({
            "budget_id": bid,
            "change": change,
            "from_total": (b or {}).get("total"),
            "to_total": (t or {}).get("total"),
            "from_status": (b or {}).get("status"),
            "to_status": (t or {}).get("status"),
        })

    return {
        "project": base.project_id,
        "from_version": base.version_number,
        "to_version": target.version_number,
        "models": model_diffs,
        "budgets": budget_diffs,
    }
