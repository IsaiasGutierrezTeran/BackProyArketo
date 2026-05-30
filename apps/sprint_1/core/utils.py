"""Cross-cutting helpers."""

from __future__ import annotations

from django.conf import settings


def absolute_media_url(file_field, request=None) -> str | None:
    """Return an absolute URL for a FileField/ImageField value.

    Mobile and external clients cannot use relative or ``localhost`` URLs, so we
    build a fully-qualified one. ``PUBLIC_BASE_URL`` (if set) wins; otherwise we
    derive it from the incoming request.
    """
    if not file_field:
        return None
    url = file_field.url
    # S3/MinIO already return a fully-qualified URL — use it as-is.
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if settings.PUBLIC_BASE_URL:
        return f"{settings.PUBLIC_BASE_URL}{url}"
    if request is not None:
        return request.build_absolute_uri(url)
    return url
