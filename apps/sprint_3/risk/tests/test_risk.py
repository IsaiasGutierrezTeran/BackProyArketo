"""CU10/CU11 — risk analysis with the deterministic mock analyzer."""

from __future__ import annotations

import pytest

from modeling.services import create_model_from_scene
from projects.models import Project

pytestmark = pytest.mark.django_db

# Long wall (8 m), narrow door (0.7 m), large area (8x6=48 m²) -> several findings.
SCENE = {
    "walls": [{"id": "w1", "start": {"x": 0, "y": 0}, "end": {"x": 8, "y": 0}, "thickness": 0.15, "height": 2.7}],
    "doors": [{"id": "d1", "width": 0.7, "position": {"x": 4, "y": 0}}],
    "windows": [],
    "bounds": {"min_x": 0, "min_y": 0, "max_x": 8, "max_y": 6},
    "image": {"unit": "meters"},
}


def test_analyze_flags_long_wall(make_user, auth_client):
    user = make_user()
    project = Project.objects.create(owner=user, name="P")
    model = create_model_from_scene(project=project, scene_json=SCENE)
    client = auth_client(user)
    resp = client.post("/api/risk/analyze", {"model3d": model.id}, format="json")
    assert resp.status_code == 201
    findings = resp.json()["data"]["findings"]
    assert any(f["category"] == "muros" and f["severity"] == "high" for f in findings)
    assert all(f["suggestion"] for f in findings)  # every finding has a mitigation


def test_cannot_analyze_others_model(make_user, auth_client):
    other = make_user(email="b@x.dev")
    project = Project.objects.create(owner=other, name="P")
    model = create_model_from_scene(project=project, scene_json=SCENE)
    client = auth_client(make_user(email="a@x.dev"))
    resp = client.post("/api/risk/analyze", {"model3d": model.id}, format="json")
    assert resp.status_code == 404
