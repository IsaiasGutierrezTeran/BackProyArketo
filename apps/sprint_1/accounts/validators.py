"""Input validators for the accounts app (kept out of serializers/views)."""

from __future__ import annotations

import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

_PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{6,30}$")


def validate_user_password(value: str) -> str:
    """Run Django's configured password validators, surfacing DRF errors."""
    try:
        validate_password(value)
    except Exception as exc:  # django ValidationError -> DRF ValidationError
        messages = getattr(exc, "messages", [str(exc)])
        raise serializers.ValidationError(messages) from exc
    return value


def validate_phone(value: str) -> str:
    if value and not _PHONE_RE.match(value):
        raise serializers.ValidationError("Número de teléfono inválido.")
    return value
