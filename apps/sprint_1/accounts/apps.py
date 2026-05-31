from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Sprint 1 — acceso (login/registro/logout/refresh), usuarios y perfil."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Cuentas y acceso"
