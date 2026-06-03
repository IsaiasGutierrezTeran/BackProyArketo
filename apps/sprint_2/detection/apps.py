from django.apps import AppConfig


class DetectionConfig(AppConfig):
    """Sprint 2 — CU5 detección IA (Mask R-CNN vía floorplan-api, o Mock)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "detection"
    verbose_name = "Detección IA"
