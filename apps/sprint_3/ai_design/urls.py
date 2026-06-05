"""AI design routes, mounted under /api/ -> /api/ai-design/."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AssistantView,
    DesignRequestViewSet,
    GenerateFromAudioView,
    GenerateFromTextView,
)

router = DefaultRouter()
router.register("ai-design/requests", DesignRequestViewSet, basename="design-request")

urlpatterns = [
    path("ai-design/text", GenerateFromTextView.as_view(), name="ai-design-text"),
    path("ai-design/audio", GenerateFromAudioView.as_view(), name="ai-design-audio"),
    path("ai-design/assistant", AssistantView.as_view(), name="ai-design-assistant"),
    *router.urls,
]
