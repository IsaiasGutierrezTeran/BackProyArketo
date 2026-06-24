"""AI design requests: generate a plan/3D model from text, audio or chat."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class DesignMode(models.TextChoices):
    TEXT = "text", "Texto"
    AUDIO = "audio", "Audio"
    ASSISTANT = "assistant", "Asistente"


class DesignStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    COMPLETED = "completed", "Completado"
    FAILED = "failed", "Fallido"


class DesignRequest(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="design_requests",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="design_requests",
    )
    mode = models.CharField(max_length=12, choices=DesignMode.choices)
    prompt_text = models.TextField(blank=True)
    audio_file = models.FileField(
        upload_to="ai_design/audio/", null=True, blank=True
    )
    transcript = models.TextField(blank=True)
    provider = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=12,
        choices=DesignStatus.choices,
        default=DesignStatus.PENDING,
    )
    # {"scene": {...}} for generation; {"messages": [...]} for the assistant.
    result = models.JSONField(null=True, blank=True)
    model3d = models.ForeignKey(
        "modeling.Model3D",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="design_request",
    )
    error = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"DesignRequest #{self.pk} ({self.mode}, {self.status})"


class AiConversation(BaseModel):
    """Historial del chat de Diseño con IA por usuario (persistido en la BD)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversation",
    )
    # Lista de turnos del chat: [{role, text, result?}], tal como los muestra el front.
    turns = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return (
            f"AiConversation({self.user_id}, {len(self.turns or [])} turnos)"
        )
