from django.apps import AppConfig


class BillingConfig(AppConfig):
    """Sprint 3 — HU-17 planes de suscripción + pagos (Stripe / Mock)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Suscripciones y pagos"
