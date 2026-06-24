"""HU-16 — incremental sync endpoint (delta by ?since=)."""

from __future__ import annotations

import pytest

from projects.models import Project

pytestmark = pytest.mark.django_db


def test_sync_returns_changes_then_empty_delta(make_user, auth_client):
    user = make_user()
    client = auth_client(user)
    Project.objects.create(owner=user, name="P1")

    first = client.get("/api/projects/sync/")
    assert first.status_code == 200
    data = first.json()["data"]
    assert data["count"] == 1
    assert data["changed"][0]["name"] == "P1"
    server_time = data["server_time"]

    # Nothing changed since the last sync -> empty delta.
    again = client.get("/api/projects/sync/", {"since": server_time})
    assert again.json()["data"]["count"] == 0

    # A new project shows up in the next delta.
    Project.objects.create(owner=user, name="P2")
    delta = client.get("/api/projects/sync/", {"since": server_time})
    names = [p["name"] for p in delta.json()["data"]["changed"]]
    assert names == ["P2"]


def test_sync_rejects_invalid_since(make_user, auth_client):
    client = auth_client(make_user())
    assert (
        client.get("/api/projects/sync/", {"since": "not-a-date"}).status_code
        == 400
    )
