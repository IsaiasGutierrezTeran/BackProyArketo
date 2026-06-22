"""Plan upload: format validation + project scoping."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Role
from plans.models import Plan
from projects.models import Project

pytestmark = pytest.mark.django_db

_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _png(name="plan.png"):
    return SimpleUploadedFile(name, _PNG, content_type="image/png")


def test_upload_plan_ok(make_user, auth_client):
    user = make_user(role=Role.ARQUITECTO)
    project = Project.objects.create(owner=user, name="P")
    client = auth_client(user)
    resp = client.post(
        "/api/plans/", {"project": project.id, "file": _png()}, format="multipart"
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["original_format"] == "png"
    assert body["file_url"].endswith(".png")
    assert Plan.objects.count() == 1


def test_reject_bad_format(make_user, auth_client):
    user = make_user(role=Role.ARQUITECTO)
    project = Project.objects.create(owner=user, name="P")
    client = auth_client(user)
    bad = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")
    resp = client.post(
        "/api/plans/", {"project": project.id, "file": bad}, format="multipart"
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False


def test_cannot_upload_to_others_project(make_user, auth_client):
    user = make_user(email="u1@test.dev", role=Role.ARQUITECTO)
    other = make_user(email="u2@test.dev", role=Role.ARQUITECTO)
    project = Project.objects.create(owner=other, name="Theirs")
    client = auth_client(user)
    resp = client.post(
        "/api/plans/", {"project": project.id, "file": _png()}, format="multipart"
    )
    assert resp.status_code == 404


def test_cliente_cannot_upload_plan(make_user, auth_client):
    """Solo arquitectos diseñan: un cliente (aunque sea dueño) recibe 403."""
    user = make_user(role=Role.CLIENTE)
    project = Project.objects.create(owner=user, name="P")
    client = auth_client(user)
    resp = client.post(
        "/api/plans/", {"project": project.id, "file": _png()}, format="multipart"
    )
    assert resp.status_code == 403
