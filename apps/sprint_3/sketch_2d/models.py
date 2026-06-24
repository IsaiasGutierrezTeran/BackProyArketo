"""HU-18 — Boceto 2D generado por prompt de IA."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class SketchStatus(models.TextChoices):
    GENERADO = "generado", "Generado"
    ERROR = "error", "Error"


class Boceto2D(BaseModel):
    """Un boceto/plano 2D (imagen) generado a partir de un prompt."""

    proyecto = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bocetos",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bocetos",
    )
    prompt = models.TextField()
    # Archivo real (storage local o S3). La URL absoluta NO se persiste: el
    # serializer la calcula al leer (en S3 es prefirmada y caduca en ~1h, así que
    # debe regenerarse en cada respuesta).
    imagen = models.ImageField(upload_to="sketch2d/", null=True, blank=True)
    proveedor_ia = models.CharField(
        max_length=20, default="mock"
    )  # mock | gemini
    estado = models.CharField(
        max_length=15,
        choices=SketchStatus.choices,
        default=SketchStatus.GENERADO,
    )
    # created_at / updated_at provienen de BaseModel.

    def __str__(self) -> str:
        return f"Boceto2D #{self.pk} ({self.estado})"
