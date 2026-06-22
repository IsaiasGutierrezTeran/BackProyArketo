"""CU14 — collaboration: membership grants visibility; viewers are read-only."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from projects.models import MembershipRole, Project, ProjectMembership

pytestmark = pytest.mark.django_db


def test_invite_is_pending_until_accepted(make_user, auth_client):
    """Invite by user id -> PENDING; the invitee only sees the project after accepting."""
    owner = make_user(email="o@x.dev")
    editor = make_user(email="e@x.dev")
    project = Project.objects.create(owner=owner, name="P")

    # Owner invites the picked user (by id), starts PENDING.
    invited = auth_client(owner).post(
        f"/api/projects/{project.id}/members/",
        {"user": editor.id, "role": "editor"}, format="json",
    )
    assert invited.status_code == 201
    assert invited.json()["data"]["status"] == "pending"

    # Before accepting: project is NOT visible, but the invitation is in the inbox.
    before = auth_client(editor).get("/api/projects/").json()
    assert not any(p["id"] == project.id for p in before["data"])
    inbox = auth_client(editor).get("/api/invitations/").json()["data"]
    assert len(inbox) == 1 and inbox[0]["project"] == project.id
    membership_id = inbox[0]["id"]

    # Accept -> now visible.
    accepted = auth_client(editor).post(f"/api/invitations/{membership_id}/accept/")
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "accepted"

    after = auth_client(editor).get("/api/projects/").json()
    assert any(p["id"] == project.id for p in after["data"])


def test_invitee_can_decline(make_user, auth_client):
    owner = make_user(email="od@x.dev")
    invitee = make_user(email="ed2@x.dev")
    project = Project.objects.create(owner=owner, name="P")

    auth_client(owner).post(
        f"/api/projects/{project.id}/members/",
        {"user": invitee.id, "role": "viewer"}, format="json",
    )
    inbox = auth_client(invitee).get("/api/invitations/").json()["data"]
    membership_id = inbox[0]["id"]

    declined = auth_client(invitee).post(f"/api/invitations/{membership_id}/decline/")
    assert declined.status_code == 204
    assert auth_client(invitee).get("/api/invitations/").json()["data"] == []


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
