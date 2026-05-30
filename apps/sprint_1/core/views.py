"""Root discovery endpoint."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@extend_schema(tags=["meta"], summary="Service discovery / liveness")
@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(_request: Request) -> Response:
    """Tiny discovery endpoint listing the available API groups."""
    return Response(
        {
            "service": "arketo-backend",
            "status": "ok",
            "docs": "/api/docs",
            "schema": "/api/schema",
            "endpoints": {
                "auth": "/api/auth/",
                "users": "/api/users/",
                "projects": "/api/projects/",
            },
        }
    )
