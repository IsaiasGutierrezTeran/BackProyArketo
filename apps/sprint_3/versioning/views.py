"""Versioning endpoints (CU15): commit, history, restore."""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.exceptions import ApiException

from . import services
from .serializers import CommitSerializer, ProjectVersionSerializer


@extend_schema(tags=["versioning"])
class ProjectVersionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """History of versions (filter with ?project=<id>) + commit + restore."""

    serializer_class = ProjectVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return services.versions_for(user).none()
        qs = services.versions_for(user)
        project = self.request.query_params.get("project")
        return qs.filter(project=project) if project else qs

    @extend_schema(
        request=CommitSerializer,
        responses={201: ProjectVersionSerializer},
        summary="Guardar una versión (commit)",
    )
    @action(detail=False, methods=["post"])
    def commit(self, request):
        data = CommitSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        version = services.commit_version(
            user=request.user,
            project_id=data.validated_data["project"],
            message=data.validated_data.get("message", ""),
        )
        return Response(
            ProjectVersionSerializer(
                version, context={"request": request}
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={200: ProjectVersionSerializer},
        summary="Restaurar el proyecto a esta versión",
    )
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        version = services.restore_version(
            user=request.user, version=self.get_object()
        )
        return Response(
            ProjectVersionSerializer(
                version, context={"request": request}
            ).data
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "from", int, required=True, description="Id de la versión base"
            ),
            OpenApiParameter(
                "to",
                int,
                required=True,
                description="Id de la versión destino",
            ),
        ],
        responses={200: dict},
        summary="Diferencias entre dos versiones (diff tipo Git)",
    )
    @action(detail=False, methods=["get"])
    def diff(self, request):
        qs = services.versions_for(request.user)
        from_id = request.query_params.get("from")
        to_id = request.query_params.get("to")
        if not from_id or not to_id:
            raise ApiException(
                "Indica 'from' y 'to' (ids de versión).",
                code="bad_request",
                status_code=400,
            )
        base = qs.filter(pk=from_id).first()
        target = qs.filter(pk=to_id).first()
        if base is None or target is None:
            raise ApiException(
                "Versión no encontrada.", code="not_found", status_code=404
            )
        if base.project_id != target.project_id:
            raise ApiException(
                "Las versiones son de proyectos distintos.",
                code="bad_request",
                status_code=400,
            )
        return Response(services.diff_versions(base=base, target=target))
