"""3D model: retrieve (CU6), edit scene + regenerate GLB (CU7), import/export (CU8)."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from modeling.models import Model3D
from modeling.services import create_model_from_scene
from projects.models import Project

pytestmark = pytest.mark.django_db

SCENE = {
    "walls": [
        {"id": "w1", "start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 0}, "thickness": 0.15, "height": 2.7},
    ],
    "doors": [],
    "windows": [],
    "bounds": {"min_x": 0, "min_y": 0, "max_x": 3, "max_y": 0},
    "image": {"unit": "meters"},
    "meta": {"model": "mock"},
}


def _model(user):
    project = Project.objects.create(owner=user, name="P")
    return create_model_from_scene(project=project, scene_json=SCENE)


def test_retrieve_model_has_glb_url(make_user, auth_client):
    user = make_user()
    model = _model(user)
    client = auth_client(user)
    resp = client.get(f"/api/models3d/{model.id}/")
    assert resp.status_code == 200
    assert resp.json()["data"]["glb_url"].endswith(".glb")


def test_edit_scene_regenerates_glb(make_user, auth_client):
    user = make_user()
    model = _model(user)
    client = auth_client(user)
    new_scene = {**SCENE, "walls": SCENE["walls"] + [
        {"id": "w2", "start": {"x": 3, "y": 0}, "end": {"x": 3, "y": 3}, "thickness": 0.15, "height": 2.7},
    ]}
    resp = client.patch(f"/api/models3d/{model.id}/scene/", {"scene": new_scene}, format="json")
    assert resp.status_code == 200
    assert resp.json()["data"]["element_count"] == 2


def test_export_returns_glb_url(make_user, auth_client):
    user = make_user()
    model = _model(user)
    client = auth_client(user)
    resp = client.get(f"/api/models3d/{model.id}/export/")
    assert resp.status_code == 200
    assert resp.json()["data"]["format"] == "glb"


def test_plan_png_renders_image(make_user, auth_client):
    user = make_user()
    model = _model(user)
    client = auth_client(user)
    resp = client.get(f"/api/models3d/{model.id}/plan.png")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/png"
    assert resp.content[:4] == b"\x89PNG"  # raw bytes, NOT wrapped in the envelope


def test_plan_pdf_downloads_attachment(make_user, auth_client):
    user = make_user()
    model = _model(user)
    client = auth_client(user)
    resp = client.get(f"/api/models3d/{model.id}/plan.pdf")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp["Content-Disposition"] == f'attachment; filename="plano_{model.id}.pdf"'
    assert resp.content[:4] == b"%PDF"


def test_plan_png_requires_auth(make_user, api_client):
    user = make_user()
    model = _model(user)
    resp = api_client.get(f"/api/models3d/{model.id}/plan.png")
    assert resp.status_code == 401


def test_plan_png_scoped_to_user_projects(make_user, auth_client):
    owner = make_user(email="owner@test.dev")
    model = _model(owner)
    other = make_user(email="other@test.dev")
    client = auth_client(other)
    resp = client.get(f"/api/models3d/{model.id}/plan.png")
    assert resp.status_code == 404


def test_import_glb(make_user, auth_client):
    user = make_user()
    project = Project.objects.create(owner=user, name="P")
    client = auth_client(user)
    glb = SimpleUploadedFile("m.glb", b"glTF\x02\x00\x00\x00rest", content_type="model/gltf-binary")
    resp = client.post(
        "/api/models3d/import/", {"project": project.id, "file": glb}, format="multipart"
    )
    assert resp.status_code == 201
    assert Model3D.objects.filter(project=project).count() == 1
