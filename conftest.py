"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role

User = get_user_model()


@pytest.fixture(autouse=True)
def _tmp_media(settings, tmp_path):
    """Isolate uploaded/generated files (plans, GLBs) in a temp dir per test run."""
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def make_user(db):
    """Factory creating users with a given role."""

    def _make(email: str = "user@test.dev", password: str = "Testpass123",
              role: str = Role.CLIENTE, **extra):
        is_super = role == Role.SUPERADMIN
        return User.objects.create_user(
            email=email, password=password, role=role,
            is_staff=is_super, is_superuser=is_super, **extra,
        )

    return _make


@pytest.fixture
def auth_client(api_client):
    """Return an APIClient authenticated as the given user (Bearer access token)."""

    def _auth(user) -> APIClient:
        access = RefreshToken.for_user(user).access_token
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return api_client

    return _auth
