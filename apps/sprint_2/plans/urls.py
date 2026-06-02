"""Plan routes, mounted under /api/ -> /api/plans/."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import PlanViewSet

router = DefaultRouter()
router.register("plans", PlanViewSet, basename="plan")

urlpatterns = router.urls
