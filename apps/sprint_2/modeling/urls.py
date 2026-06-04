"""3D model routes, mounted under /api/ -> /api/models3d/."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import Model3DViewSet

router = DefaultRouter()
router.register("models3d", Model3DViewSet, basename="model3d")

urlpatterns = router.urls
