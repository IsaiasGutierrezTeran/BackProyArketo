"""Endpoints de HU-18 (las views solo orquestan)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Boceto2D
from .serializers import Boceto2DSerializer, GenerateSketchSerializer


@extend_schema(tags=["sketch2d"])
class GenerateSketchView(APIView):
    """POST /api/sketch2d/generate — genera un boceto 2D desde un prompt."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=GenerateSketchSerializer,
        responses={201: Boceto2DSerializer},
        summary="Generar boceto/plano 2D por prompt (IA)",
    )
    def post(self, request):
        data = GenerateSketchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        boceto = services.generate_sketch(
            user=request.user,
            prompt=data.validated_data["prompt"],
            project_id=data.validated_data.get("project"),
            provider_name=data.validated_data.get("provider"),
        )
        return Response(
            Boceto2DSerializer(boceto, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["sketch2d"])
class Sketch2DViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """GET /api/sketch2d/ — bocetos del usuario."""

    serializer_class = Boceto2DSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return Boceto2D.objects.none()
        return services.sketches_for(user)
