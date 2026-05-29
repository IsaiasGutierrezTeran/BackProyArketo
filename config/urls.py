"""Root URL configuration for the Arketo backend.

API endpoints live under ``/api/``. OpenAPI schema and Swagger UI are served by
drf-spectacular. Uploaded media is served by Django only in DEBUG; in production
a real web server / object store serves it.
"""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from core.views import api_root

urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    # OpenAPI / Swagger
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Sprint 1 apps
    path("api/auth/", include("accounts.urls")),
    path("api/", include("accounts.admin_urls")),
    path("api/", include("projects.urls")),
    # Sprint 2 apps (digitalización 2D->3D)
    path("api/", include("plans.urls")),
    path("api/", include("detection.urls")),
    path("api/", include("modeling.urls")),
    # Sprint 3 apps (IA y presupuesto)
    path("api/", include("ai_design.urls")),
    path("api/", include("risk.urls")),
    path("api/", include("budget.urls")),
    path("api/", include("sketch_2d.urls")),
    # Sprint 4 apps (colaboración y pagos)
    path("api/", include("versioning.urls")),
    path("api/", include("billing.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
