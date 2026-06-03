"""Detection routes, mounted under /api/ -> /api/detection/."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DetectionJobViewSet, RunDetectionView

router = DefaultRouter()
router.register("detection/jobs", DetectionJobViewSet, basename="detection-job")

urlpatterns = [
    path("detection/run", RunDetectionView.as_view(), name="detection-run"),
    *router.urls,
]
