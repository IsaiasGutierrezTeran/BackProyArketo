"""Base settings shared by every environment (Arketo backend).

Everything environment-specific is read from environment variables / a local
`.env` file (see `.env.example`). No secret, host or credential is hard-coded.
PostgreSQL is mandatory — there is intentionally no SQLite fallback.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# BASE_DIR -> the `BACKEND/` project root (this file is config/settings/base.py).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Apps are grouped on disk by Scrum sprint under `apps/sprint_N/` (for traceability
# code <-> documentation). Each sprint folder is added to sys.path so every app
# stays importable by its short name (`core`, `accounts`, ...), keeping imports,
# app labels and migrations unchanged regardless of which sprint folder it lives in.
APPS_ROOT = BASE_DIR / "apps"
SPRINT_PACKAGES = ["sprint_1", "sprint_2", "sprint_3"]
for _sprint in SPRINT_PACKAGES:
    _path = str(APPS_ROOT / _sprint)
    if _path not in sys.path:
        sys.path.insert(0, _path)

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Public base URL used to build absolute media URLs reachable from mobile.
# Empty -> derived from the incoming request (request.build_absolute_uri).
PUBLIC_BASE_URL = (env("PUBLIC_BASE_URL", "") or "").rstrip("/")

# --- Applications -----------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
]

# Local apps are added per Sprint (grouped on disk under apps/sprint_N/).
LOCAL_APPS = [
    # Sprint 1 — base
    "core",
    "accounts",
    "projects",
    # Sprint 2 — digitalización 2D->3D
    "plans",
    "detection",
    "modeling",
    # Sprint 3 — presupuesto, colaboración, pagos y boceto 2D
    "ai_design",
    "risk",
    "budget",
    "sketch_2d",
    "versioning",
    "billing",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database (PostgreSQL only) --------------------------------------------
_database_url = (env("DATABASE_URL", "") or "").strip()
if not _database_url:
    raise ImproperlyConfigured(
        "DATABASE_URL is required (PostgreSQL). Copy .env.example to .env and set it, "
        "or run `docker compose up -d db`. SQLite is intentionally not supported."
    )
DATABASES = {"default": dj_database_url.parse(_database_url, conn_max_age=600)}

# --- Auth -------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- DRF + JWT + OpenAPI ----------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "core.renderers.EnvelopeJSONRenderer",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Throttling: solo afecta a vistas con `throttle_scope` (p.ej. login, HU-2).
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {"login": env("LOGIN_THROTTLE_RATE", "10/min")},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Arketo API",
    "DESCRIPTION": (
        "Backend de Arketo — Plataforma de Inteligencia Espacial para coordinación "
        "de obras, control presupuestario y digitalización de planos 2D→3D. "
        "Todas las respuestas usan el envelope estándar "
        "`{success, data, meta}` (éxito) / `{success, error}` (error)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "POSTPROCESSING_HOOKS": ["core.openapi.envelope_postprocessing_hook"],
    "COMPONENT_SPLIT_REQUEST": True,
}

# --- CORS (browser clients; Flutter native ignores this) --------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:4200")
CORS_ALLOW_CREDENTIALS = True

# --- I18N -------------------------------------------------------------------
LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static & media ---------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Uploads: max size enforced by validators (used by plans in Sprint 2).
MAX_UPLOAD_SIZE_MB = float(env("MAX_UPLOAD_SIZE_MB", "20"))

# --- File storage: local (default) or S3/MinIO, switchable by USE_S3 --------
# Local en desarrollo; S3 (AWS) o MinIO (S3-compatible) en producción. Las URLs
# que devuelve la API siguen siendo absolutas en ambos casos (ver core.utils).
USE_S3 = env_bool("USE_S3", False)
if USE_S3:
    # Empty -> None so boto3 / django-storages fall back to the default AWS
    # credential chain (the EC2 instance role): NO keys are stored in prod.
    # Set these only for MinIO / local-dev S3.
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID") or None
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY") or None
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", "us-east-1")
    # MinIO / S3-compatible: set the endpoint (empty -> real AWS S3).
    AWS_S3_ENDPOINT_URL = (env("AWS_S3_ENDPOINT_URL", "") or "").strip() or None
    AWS_S3_USE_SSL = env_bool("AWS_S3_USE_SSL", True)
    AWS_S3_ADDRESSING_STYLE = env("AWS_S3_ADDRESSING_STYLE", "auto")  # 'path' for MinIO
    # Private bucket in prod -> presigned (querystring-auth) URLs so the mobile
    # app / 3D viewer can load media directly. AWS_QUERYSTRING_AUTH=true in prod;
    # set false only for a public bucket / MinIO.
    AWS_QUERYSTRING_AUTH = env_bool("AWS_QUERYSTRING_AUTH", False)
    AWS_QUERYSTRING_EXPIRE = int(env("AWS_QUERYSTRING_EXPIRE", "3600"))
    AWS_DEFAULT_ACL = env("AWS_DEFAULT_ACL", "") or None
    AWS_S3_FILE_OVERWRITE = False
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3.S3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Detection / 2D->3D (Sprint 2) ------------------------------------------
# Default detector keeps dev unblocked without GPU/weights/legacy service.
DETECTION_DEFAULT_DETECTOR = env("DETECTION_DEFAULT_DETECTOR", "mock")  # mock | maskrcnn
# Real-world extrusion defaults (meters) for GLB generation.
WALL_HEIGHT_M = float(env("WALL_HEIGHT_M", "2.7"))
DEFAULT_WALL_THICKNESS_M = float(env("DEFAULT_WALL_THICKNESS_M", "0.15"))

# --- Integrations (used in later sprints) -----------------------------------
FLOORPLAN_API_URL = (env("FLOORPLAN_API_URL", "http://127.0.0.1:8000") or "").rstrip("/")
FLOORPLAN_API_TIMEOUT = float(env("FLOORPLAN_API_TIMEOUT", "120"))
# --- AI design / risk (Sprint 3) — mock by default; gemini or aws opt-in -----
AI_DESIGN_PROVIDER = env("AI_DESIGN_PROVIDER", "mock")  # mock | gemini | aws
RISK_ANALYZER = env("RISK_ANALYZER", "mock")  # mock | gemini | aws
SPEECH_TO_TEXT_PROVIDER = env("SPEECH_TO_TEXT_PROVIDER", "mock")  # mock | gemini | aws
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-1.5-flash")

# --- AWS managed AI (the "aws" provider): Bedrock (Claude) + Transcribe ------
# Credentials come from the EC2 instance role (no keys). Region defaults to the
# S3 region. Model id is configurable; default = Claude Haiku 4.5 on Bedrock.
AWS_REGION = env("AWS_REGION", env("AWS_S3_REGION_NAME", "us-east-1"))
BEDROCK_MODEL_ID = env("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
TRANSCRIBE_LANGUAGE = env("TRANSCRIBE_LANGUAGE", "es-US")

# --- Budget (Sprint 3) ------------------------------------------------------
DEFAULT_CURRENCY = env("DEFAULT_CURRENCY", "Bs")  # bolivianos

# --- Sketch 2D (Sprint 3, HU-18) — boceto 2D por prompt; mock por defecto ---
SKETCH_PROVIDER = env("SKETCH_PROVIDER", "mock")  # mock | gemini

GEMINI_API_KEY = env("GEMINI_API_KEY", "")

# --- Billing (Sprint 3) — mock gateway by default, Stripe opt-in ------------
BILLING_GATEWAY = env("BILLING_GATEWAY", "mock")  # mock | stripe
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")
BILLING_SUCCESS_URL = env("BILLING_SUCCESS_URL", "http://localhost:4200/billing/success")
BILLING_CANCEL_URL = env("BILLING_CANCEL_URL", "http://localhost:4200/billing/cancel")
