"""Development settings."""

from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)

# Relaxed for local web/mobile development.
ALLOWED_HOSTS = ["*"]

# Allow any origin in dev so the Flutter model_viewer WebView (and the Angular
# dev server on any port) can fetch the .glb from /media/ without CORS blocks.
# In production, CORS for the GLBs is handled by the S3 bucket's CORS policy.
CORS_ALLOW_ALL_ORIGINS = True
