"""HU-15 — diff between two project versions."""

from __future__ import annotations

import pytest

from modeling.models import Model3D
from projects.models import Project

pytestmark = pytest.mark.django_db


def _scene(n_walls: int) -> dict:
    return {
        "walls": [
            {
                "start": {"x": 0, "y": i},
                "end": {"x": 3, "y": i},
                "thickness": 0.15,
                "height": 2.7,
            }
            for i in range(n_walls)
        ]
    }


def test_diff_reports_modified_model(make_user, auth_client):
    user = make_user()
    client = auth_client(user)
    project = Project.objects.create(owner=user, name="P")
    model = Model3D.objects.create(
        project=project, scene_json=_scene(1), element_count=1, is_current=True
    )

    v1 = client.post(
        "/api/versions/commit/",
        {"project": project.id, "message": "v1"},
        format="json",
    ).json()["data"]

    model.scene_json = _scene(3)
    model.save(update_fields=["scene_json"])
    v2 = client.post(
        "/api/versions/commit/",
        {"project": project.id, "message": "v2"},
        format="json",
    ).json()["data"]

    resp = client.get(
        "/api/versions/diff/", {"from": v1["id"], "to": v2["id"]}
    )
    assert resp.status_code == 200
    diff = resp.json()["data"]
    assert diff["from_version"] == v1["version_number"]
    assert diff["to_version"] == v2["version_number"]
    changed = [m for m in diff["models"] if m["model_id"] == model.id]
    assert changed and changed[0]["change"] == "modified"
    assert changed[0]["from_counts"]["walls"] == 1
    assert changed[0]["to_counts"]["walls"] == 3


def test_diff_requires_both_versions(make_user, auth_client):
    client = auth_client(make_user())
    assert client.get("/api/versions/diff/", {"from": 1}).status_code == 400
