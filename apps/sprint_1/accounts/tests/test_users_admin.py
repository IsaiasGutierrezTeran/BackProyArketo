"""User CRUD is restricted to superadmin; other roles get 403."""

from __future__ import annotations

import pytest

from accounts.models import Role

pytestmark = pytest.mark.django_db


def test_cliente_cannot_list_users(make_user, auth_client):
    cliente = make_user(email="c@test.dev", role=Role.CLIENTE)
    client = auth_client(cliente)
    resp = client.get("/api/users/")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_superadmin_can_create_and_list_users(make_user, auth_client):
    admin = make_user(email="root@test.dev", role=Role.SUPERADMIN)
    client = auth_client(admin)

    created = client.post(
        "/api/users/",
        {
            "email": "ing@test.dev",
            "password": "Str0ngPass123",
            "role": "ingeniero",
            "full_name": "Ing",
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["data"]["role"] == "ingeniero"

    listed = client.get("/api/users/")
    assert listed.status_code == 200
    body = listed.json()
    # paginated list -> data is a list, pagination under meta
    assert isinstance(body["data"], list)
    assert "pagination" in body["meta"]
    assert body["meta"]["pagination"]["count"] >= 2
