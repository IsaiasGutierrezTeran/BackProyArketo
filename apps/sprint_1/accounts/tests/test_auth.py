"""Critical auth flow: register -> login -> me -> refresh -> logout, + envelope."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_register_returns_enveloped_user(api_client):
    resp = api_client.post(
        "/api/auth/register",
        {
            "email": "new@test.dev",
            "password": "Str0ngPass123",
            "full_name": "New User",
        },
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["email"] == "new@test.dev"
    assert body["data"]["role"] == "cliente"  # never self-escalates


def test_login_returns_tokens_and_user(api_client, make_user):
    make_user(email="log@test.dev", password="Str0ngPass123")
    resp = api_client.post(
        "/api/auth/login",
        {"email": "log@test.dev", "password": "Str0ngPass123"},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access" in data and "refresh" in data
    assert data["user"]["email"] == "log@test.dev"


def test_login_bad_credentials_uses_error_envelope(api_client, make_user):
    make_user(email="log2@test.dev", password="Str0ngPass123")
    resp = api_client.post(
        "/api/auth/login",
        {"email": "log2@test.dev", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "unauthorized"


def test_me_requires_auth_and_returns_profile(
    api_client, make_user, auth_client
):
    user = make_user(email="me@test.dev")
    assert api_client.get("/api/auth/me").status_code == 401  # no token

    client = auth_client(user)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "me@test.dev"


def test_patch_me_updates_profile(make_user, auth_client):
    user = make_user(email="edit@test.dev")
    client = auth_client(user)
    resp = client.patch(
        "/api/auth/me", {"full_name": "Edited Name"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["full_name"] == "Edited Name"


def test_refresh_then_logout(api_client, make_user):
    make_user(email="ref@test.dev", password="Str0ngPass123")
    login = api_client.post(
        "/api/auth/login",
        {"email": "ref@test.dev", "password": "Str0ngPass123"},
        format="json",
    ).json()["data"]

    refreshed = api_client.post(
        "/api/auth/refresh", {"refresh": login["refresh"]}, format="json"
    )
    assert refreshed.status_code == 200
    assert "access" in refreshed.json()["data"]

    # logout needs auth + the (rotated) refresh token to blacklist
    new_refresh = refreshed.json()["data"].get("refresh", login["refresh"])
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    out = api_client.post(
        "/api/auth/logout", {"refresh": new_refresh}, format="json"
    )
    assert out.status_code == 200
    assert out.json()["success"] is True
