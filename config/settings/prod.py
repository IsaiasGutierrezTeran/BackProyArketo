"""Production settings (hardened defaults; everything still env-driven)."""

from __future__ import annotations

from .base import *  # noqa: F401,F403

DEBUG = False

# Security headers — enabled behind TLS termination.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
