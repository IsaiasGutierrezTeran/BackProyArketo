"""CU15 — commit a version, then restore it (geometry rolls back)."""

from __future__ import annotations

import pytest

from modeling.services import create_model_from_scene, replace_scene
from projects.models import Project

pytestmark = pytest.mark.django_db

ONE_WALL = {
    "walls": [{"id": "w1", "start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 0}, "thickness": 0.15, "height": 2.7}],
    "doors": [], "windows": [], "bounds": {}, "image": {"unit": "meters"}, "meta": {},
}
TWO_WALLS = {
    **ONE_WALL,
    "walls": ONE_WALL["walls"] + [
        {"id": "w2", "start": {"x": 3, "y": 0}, "end": {"x": 3, "y": 3}, "thickness": 0.15, "height": 2.7}
    ],
}


def test_commit_then_restore_rolls_back(make_user, auth_client):
    user = make_user()
    project = Project.objects.create(owner=user, name="P")
    model = create_model_from_scene(project=project, scene_json=ONE_WALL)
    client = auth_client(user)

    committed = client.post(
        "/api/versions/commit/", {"project": project.id, "message": "v1"}, format="json"
    )
    assert committed.status_code == 201
    assert committed.json()["data"]["version_number"] == 1
    version_id = committed.json()["data"]["id"]

    # Edit the model to two walls, then restore v1.
    replace_scene(model=model, scene_json=TWO_WALLS)
    model.refresh_from_db()
    assert model.element_count == 2

    restored = client.post(f"/api/versions/{version_id}/restore/")
    assert restored.status_code == 200
    model.refresh_from_db()
    assert model.element_count == 1
