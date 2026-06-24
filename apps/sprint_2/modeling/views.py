"""3D model endpoints: view/navigate (CU6), edit (CU7), import/export (CU8)."""

from __future__ import annotations

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.exceptions import ApiException
from core.permissions import IsArquitecto
from core.utils import absolute_media_url
from projects.services import assert_can_edit_project, projects_for

from . import plan2d, services
from .models import Model3D
from .serializers import (
    ImportGlbSerializer,
    Model3DSerializer,
    SceneEditSerializer,
)

# Acciones que MODIFICAN el modelo/diseño: exclusivas del arquitecto.
_DESIGN_ACTIONS = {"scene", "import_model", "destroy"}


@extend_schema(tags=["modeling"])
class Model3DViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """View (any member), edit/import/delete (arquitecto) 3D models in the user's projects."""

    serializer_class = Model3DSerializer

    def get_permissions(self):
        return (
            [IsArquitecto()]
            if self.action in _DESIGN_ACTIONS
            else [IsAuthenticated()]
        )

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return Model3D.objects.none()
        qs = Model3D.objects.filter(project__in=projects_for(user))
        project = self.request.query_params.get("project")
        return qs.filter(project=project) if project else qs

    @extend_schema(
        request=SceneEditSerializer,
        responses={200: Model3DSerializer},
        summary="Editar la arquitectura (mover/escalar/eliminar) y regenerar el GLB",
    )
    @action(detail=True, methods=["patch"])
    def scene(self, request, pk=None):
        model = self.get_object()
        assert_can_edit_project(request.user, model.project)
        data = SceneEditSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        model = services.replace_scene(
            model=model, scene_json=data.validated_data["scene"]
        )
        return Response(
            Model3DSerializer(model, context={"request": request}).data
        )

    @extend_schema(
        summary="Exportar el modelo (URL del GLB)", responses={200: None}
    )
    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        model = self.get_object()
        return Response(
            {
                "format": "glb",
                "glb_url": absolute_media_url(model.glb_file, request),
            }
        )

    @extend_schema(
        summary="Renderizar el plano 2D (PNG) al vuelo desde la escena del modelo",
        responses={200: OpenApiResponse(description="Imagen PNG del plano")},
    )
    @action(detail=True, methods=["get"], url_path="plan.png")
    def plan_png(self, request, pk=None):
        model = self.get_object()
        png = plan2d.render_png(model.scene_json or {})
        return HttpResponse(png, content_type="image/png")

    @extend_schema(
        summary="Renderizar el plano 2D (PDF) al vuelo desde la escena del modelo",
        responses={
            200: OpenApiResponse(description="Documento PDF del plano")
        },
    )
    @action(detail=True, methods=["get"], url_path="plan.pdf")
    def plan_pdf(self, request, pk=None):
        model = self.get_object()
        pdf = plan2d.render_pdf(model.scene_json or {})
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="plano_{model.pk}.pdf"'
        )
        return response

    @extend_schema(
        request=ImportGlbSerializer,
        responses={201: Model3DSerializer},
        summary="Importar un modelo 3D externo (GLB/GLTF) a un proyecto",
    )
    @action(detail=False, methods=["post"], url_path="import")
    def import_model(self, request):
        data = ImportGlbSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        project = (
            projects_for(request.user)
            .filter(pk=data.validated_data["project"])
            .first()
        )
        if project is None:
            raise ApiException(
                "Proyecto no encontrado.", code="not_found", status_code=404
            )
        assert_can_edit_project(request.user, project)
        model = services.import_glb(
            project=project, glb_file=data.validated_data["file"]
        )
        return Response(
            Model3DSerializer(model, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
