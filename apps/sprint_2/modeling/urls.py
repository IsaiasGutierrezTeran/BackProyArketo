"""3D model routes, mounted under /api/ -> /api/models3d/."""

from __future__ import annotations

from django.urls import re_path
from rest_framework.routers import DefaultRouter

from .views import Model3DViewSet

router = DefaultRouter()
router.register("models3d", Model3DViewSet, basename="model3d")

# Explicit no-trailing-slash routes for the on-the-fly 2D plan downloads so the
# URLs are exactly /api/models3d/{id}/plan.png and /plan.pdf (the router would
# otherwise append a trailing slash). These reuse the ViewSet actions, so they
# inherit IsAuthenticated/JWT and get_object() unchanged.
_plan_png = Model3DViewSet.as_view({"get": "plan_png"})
_plan_pdf = Model3DViewSet.as_view({"get": "plan_pdf"})

urlpatterns = [
    re_path(
        r"^models3d/(?P<pk>[^/.]+)/plan\.png$",
        _plan_png,
        name="model3d-plan-png",
    ),
    re_path(
        r"^models3d/(?P<pk>[^/.]+)/plan\.pdf$",
        _plan_pdf,
        name="model3d-plan-pdf",
    ),
    *router.urls,
]
