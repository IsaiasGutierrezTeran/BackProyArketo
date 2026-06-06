"""Risk endpoints (CU10/CU11): analyze a model + browse past analyses."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.services import projects_for

from . import services
from .models import RiskAnalysis
from .serializers import AnalyzeSerializer, RiskAnalysisSerializer


@extend_schema(tags=["risk"])
class AnalyzeRiskView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AnalyzeSerializer, responses={201: RiskAnalysisSerializer},
                   summary="Analizar riesgos estructurales de un modelo 3D")
    def post(self, request):
        data = AnalyzeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        model = services.model_for_user(request.user, data.validated_data["model3d"])
        analysis = services.analyze_model(
            user=request.user, model3d=model,
            analyzer_name=data.validated_data.get("analyzer"),
        )
        return Response(
            RiskAnalysisSerializer(analysis, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["risk"])
class RiskAnalysisViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = RiskAnalysisSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return RiskAnalysis.objects.none()
        return RiskAnalysis.objects.filter(
            model3d__project__in=projects_for(user)
        ).prefetch_related("findings")
