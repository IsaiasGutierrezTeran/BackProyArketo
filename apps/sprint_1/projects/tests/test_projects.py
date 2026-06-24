"""Projects are owner-scoped; dashboard summarizes the caller's projects."""

from __future__ import annotations

import pytest

from accounts.models import Role
from projects.models import Project

pytestmark = pytest.mark.django_db


def test_create_project_sets_owner(make_user, auth_client):
    user = make_user(email="owner@test.dev")
    client = auth_client(user)
    resp = client.post(
        "/api/projects/",
        {"name": "Mi casa", "description": "demo"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "Mi casa"
    assert Project.objects.get().owner == user


def test_list_is_scoped_to_owner(make_user, auth_client):
    owner = make_user(email="a@test.dev")
    other = make_user(email="b@test.dev")
    Project.objects.create(owner=owner, name="A-project")
    Project.objects.create(owner=other, name="B-project")

    client = auth_client(owner)
    body = client.get("/api/projects/").json()
    names = [p["name"] for p in body["data"]]
    assert names == ["A-project"]  # cannot see other's project


def test_cannot_edit_others_project(make_user, auth_client):
    owner = make_user(email="o1@test.dev")
    other = make_user(email="o2@test.dev")
    proj = Project.objects.create(owner=other, name="Theirs")

    client = auth_client(owner)
    # Not in owner's queryset -> 404 (not even visible)
    resp = client.patch(
        f"/api/projects/{proj.id}/", {"name": "hijack"}, format="json"
    )
    assert resp.status_code == 404


def test_dashboard_summary(make_user, auth_client):
    user = make_user(email="dash@test.dev")
    Project.objects.create(owner=user, name="P1", status="active")
    Project.objects.create(owner=user, name="P2", status="draft")

    client = auth_client(user)
    resp = client.get("/api/projects/dashboard/")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert data["by_status"]["active"] == 1
    assert data["by_status"]["draft"] == 1
    assert len(data["recent"]) == 2


def test_superadmin_sees_all_projects(make_user, auth_client):
    owner = make_user(email="reg@test.dev")
    admin = make_user(email="super@test.dev", role=Role.SUPERADMIN)
    Project.objects.create(owner=owner, name="Owned")

    client = auth_client(admin)
    body = client.get("/api/projects/").json()
    assert body["meta"]["pagination"]["count"] >= 1
