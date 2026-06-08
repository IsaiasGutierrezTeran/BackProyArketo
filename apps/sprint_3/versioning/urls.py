"""Versioning routes, mounted under /api/ -> /api/versions/."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import ProjectVersionViewSet

router = DefaultRouter()
router.register("versions", ProjectVersionViewSet, basename="version")

urlpatterns = router.urls
