"""Business logic for accounts (views only orchestrate; logic lives here)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import ApiException

from .models import Role

User = get_user_model()


def register_user(*, email: str, password: str, full_name: str = "", phone: str = "") -> "User":
    """Self-registration. Role is forced to ``cliente`` to prevent escalation."""
    return User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        phone=phone,
        role=Role.CLIENTE,
    )


def update_profile(user: "User", **fields) -> "User":
    """Update the caller's own profile fields and persist."""
    allowed = {"full_name", "phone", "avatar"}
    for key, value in fields.items():
        if key in allowed:
            setattr(user, key, value)
    user.save(update_fields=[f for f in fields if f in allowed] or None)
    return user


def logout(refresh_token: str) -> None:
    """Blacklist a refresh token so it can no longer be rotated/used."""
    if not refresh_token:
        raise ApiException("El campo 'refresh' es obligatorio.", code="bad_request")
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError as exc:
        raise ApiException(
            "Token de refresco inválido o expirado.",
            code="unauthorized",
            status_code=401,
        ) from exc


def admin_create_user(*, password: str | None = None, **fields) -> "User":
    """Superadmin creates a user with an explicit role."""
    user = User(**fields)
    if password:
        user.set_password(password)
    else:
        user.set_unusable_password()
    user.save()
    return user


def admin_update_user(user: "User", *, password: str | None = None, **fields) -> "User":
    """Superadmin updates a user (optionally resetting the password)."""
    for key, value in fields.items():
        setattr(user, key, value)
    if password:
        user.set_password(password)
    user.save()
    return user


def deactivate_user(user: "User") -> "User":
    """Logical delete (baja lógica): deactivate instead of removing the row."""
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


def reactivate_user(user: "User") -> "User":
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user
