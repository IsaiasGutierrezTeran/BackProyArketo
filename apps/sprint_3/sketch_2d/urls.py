"""Rutas de HU-18, montadas en /api/ -> /api/sketch2d/."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import GenerateSketchView, Sketch2DViewSet

router = DefaultRouter()
router.register("sketch2d", Sketch2DViewSet, basename="sketch2d")

urlpatterns = [
    path("sketch2d/generate", GenerateSketchView.as_view(), name="sketch2d-generate"),
    *router.urls,
]
