"""Plan endpoints: upload + list/retrieve/delete, scoped to the user's projects."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .serializers import PlanSerializer, PlanUploadSerializer


@extend_schema(tags=["plans"])
class PlanViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Upload and manage 2D plans (no in-place update; re-upload instead)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return services.plans_for(user).none()
        qs = services.plans_for(user)
        project = self.request.query_params.get("project")
        return qs.filter(project=project) if project else qs

    def get_serializer_class(self):
        return PlanUploadSerializer if self.action == "create" else PlanSerializer

    @extend_schema(
        request=PlanUploadSerializer,
        responses={201: PlanSerializer},
        summary="Subir un plano (PDF/JPG/PNG/CSV) a un proyecto",
    )
    def create(self, request, *args, **kwargs):
        serializer = PlanUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        plan = services.create_plan(user=request.user, **serializer.validated_data)
        return Response(
            PlanSerializer(plan, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
