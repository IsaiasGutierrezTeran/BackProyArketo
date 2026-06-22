"""2D->3D pipeline with the mock detector (no GPU/network needed)."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Role
from modeling.models import Model3D
from plans.models import Plan, PlanStatus
from projects.models import Project

pytestmark = pytest.mark.django_db


def _make_plan(user):
    project = Project.objects.create(owner=user, name="P")
    return Plan.objects.create(
        project=project,
        uploaded_by=user,
        file=SimpleUploadedFile("p.png", b"x" * 32, content_type="image/png"),
        original_format="png",
        size_bytes=32,
    )


def test_run_pipeline_mock_creates_model(make_user, auth_client):
    user = make_user(role=Role.ARQUITECTO)
    plan = _make_plan(user)
    client = auth_client(user)

    resp = client.post(
        "/api/detection/run", {"plan": plan.id, "detector": "mock"}, format="json"
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "completed"
    assert data["model"]["element_count"] == 6  # 4 walls + 1 door + 1 window
    assert data["model"]["glb_url"].endswith(".glb")

    plan.refresh_from_db()
    assert plan.status == PlanStatus.PROCESSED
    assert Model3D.objects.filter(project=plan.project, is_current=True).count() == 1


def test_cannot_detect_others_plan(make_user, auth_client):
    user = make_user(email="a@x.dev", role=Role.ARQUITECTO)
    other = make_user(email="b@x.dev", role=Role.ARQUITECTO)
    plan = _make_plan(other)
    client = auth_client(user)
    resp = client.post("/api/detection/run", {"plan": plan.id}, format="json")
    assert resp.status_code == 404
