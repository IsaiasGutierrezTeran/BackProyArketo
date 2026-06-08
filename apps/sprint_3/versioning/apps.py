from django.apps import AppConfig


class VersioningConfig(AppConfig):
    """Sprint 3 — HU-15 versionado tipo Git (commit, historial, restaurar, diff)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "versioning"
    verbose_name = "Versionado"
