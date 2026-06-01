"""CU14 — collaboration: membership grants visibility; viewers are read-only."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from projects.models import MembershipRole, Project, ProjectMembership

pytestmark = pytest.mark.django_db


def test_owner_invites_member_grants_visibility(make_user, auth_client):
    owner = make_user(email="o@x.dev")
    editor = make_user(email="e@x.dev")
    project = Project.objects.create(owner=owner, name="P")

    invited = auth_client(owner).post(
        f"/api/projects/{project.id}/members/",
        {"email": "e@x.dev", "role": "editor"}, format="json",
    )
    assert invited.status_code == 201

    body = auth_client(editor).get("/api/projects/").json()
    assert any(p["id"] == project.id for p in body["data"])


def test_non_member_cannot_invite(make_user, auth_client):
    owner = make_user(email="o2@x.dev")
    outsider = make_user(email="x2@x.dev")
    project = Project.objects.create(owner=owner, name="P")
    resp = auth_client(outsider).post(
        f"/api/projects/{project.id}/members/",
        {"email": "x2@x.dev", "role": "editor"}, format="json",
    )
    assert resp.status_code in (403, 404)


def test_viewer_cannot_upload_plan(make_user, auth_client):
    owner = make_user(email="o3@x.dev")
    viewer = make_user(email="v@x.dev")
    project = Project.objects.create(owner=owner, name="P")
    ProjectMembership.objects.create(project=project, user=viewer, role=MembershipRole.VIEWER)

    png = SimpleUploadedFile("p.png", b"\x89PNG\r\n\x1a\n" + b"0" * 40, content_type="image/png")
    resp = auth_client(viewer).post(
        "/api/plans/", {"project": project.id, "file": png}, format="multipart"
    )
    assert resp.status_code == 403


def test_editor_can_comment(make_user, auth_client):
    owner = make_user(email="o4@x.dev")
    editor = make_user(email="ed@x.dev")
    project = Project.objects.create(owner=owner, name="P")
    ProjectMembership.objects.create(project=project, user=editor, role=MembershipRole.EDITOR)

    resp = auth_client(editor).post(
        "/api/comments/", {"project": project.id, "body": "buen avance"}, format="json"
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["author_email"] == "ed@x.dev"
