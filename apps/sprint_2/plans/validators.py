"""File validation for plan uploads (kept out of views)."""

from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from core.exceptions import ApiException

ALLOWED_PLAN_FORMATS = {"pdf", "jpg", "jpeg", "png", "csv"}


def normalized_format(filename: str) -> str:
    """Return the canonical extension (jpeg -> jpg), lowercased."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return "jpg" if ext == "jpeg" else ext


def validate_plan_file(file):
    """Validate extension (422) and size (413). Returns the file unchanged."""
    ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    if ext not in ALLOWED_PLAN_FORMATS:
        raise serializers.ValidationError(
            f"Formato no permitido '.{ext}'. Use: {', '.join(sorted(ALLOWED_PLAN_FORMATS))}."
        )
    max_bytes = int(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024)
    if file.size > max_bytes:
        # Propagates to the centralized handler as HTTP 413.
        raise ApiException(
            f"El archivo supera el máximo de {settings.MAX_UPLOAD_SIZE_MB} MB.",
            code="payload_too_large",
            status_code=413,
        )
    return file
