"""Risk routes, mounted under /api/ -> /api/risk/."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AnalyzeRiskView, RiskAnalysisViewSet

router = DefaultRouter()
router.register("risk/analyses", RiskAnalysisViewSet, basename="risk-analysis")

urlpatterns = [
    path("risk/analyze", AnalyzeRiskView.as_view(), name="risk-analyze"),
    *router.urls,
]
