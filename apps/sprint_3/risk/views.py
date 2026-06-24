"""Risk endpoints (CU10/CU11): analyze a model + browse past analyses."""

from __future__ import annotations

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.entitlements import requires_plan
from core.reports import risk_report_pdf
from projects.services import projects_for

from . import services
from .models import RiskAnalysis
from .serializers import AnalyzeSerializer, RiskAnalysisSerializer


@extend_schema(tags=["risk"])
class AnalyzeRiskView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=AnalyzeSerializer,
        responses={201: RiskAnalysisSerializer},
        summary="Analizar riesgos estructurales de un modelo 3D",
    )
    def post(self, request):
        requires_plan(request.user, "pro", "El análisis de riesgos con IA")
        data = AnalyzeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        model = services.model_for_user(
            request.user, data.validated_data["model3d"]
        )
        analysis = services.analyze_model(
            user=request.user,
            model3d=model,
            analyzer_name=data.validated_data.get("analyzer"),
        )
        return Response(
            RiskAnalysisSerializer(
                analysis, context={"request": request}
            ).data,
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

    @extend_schema(
        responses={200: None}, summary="Descargar el reporte de riesgos en PDF"
    )
    @action(detail=True, methods=["get"], url_path="report.pdf")
    def report_pdf(self, request, pk=None):
        analysis = self.get_object()
        resp = HttpResponse(
            risk_report_pdf(analysis), content_type="application/pdf"
        )
        resp["Content-Disposition"] = (
            f'inline; filename="riesgos-{analysis.id}.pdf"'
        )
        return resp
