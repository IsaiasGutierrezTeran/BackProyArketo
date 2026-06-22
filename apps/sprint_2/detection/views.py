"""Detection endpoints: run the pipeline + browse past jobs. Views orchestrate."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.entitlements import allowed_detectors
from core.exceptions import ApiException
from core.permissions import IsArquitecto
from plans.services import plans_for
from projects.services import assert_can_edit_project

from . import services
from .models import DetectionJob
from .serializers import DetectionJobSerializer, RunDetectionSerializer


@extend_schema(tags=["detection"])
class RunDetectionView(APIView):
    """Generate a 3D model from an uploaded plan (CU5). Arquitecto-only."""

    permission_classes = [IsArquitecto]

    @extend_schema(
        request=RunDetectionSerializer,
        responses={201: DetectionJobSerializer},
        summary="Ejecutar detección + generar modelo 3D a partir de un plano",
    )
    def post(self, request):
        data = RunDetectionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data

        plan = plans_for(request.user).filter(pk=payload["plan"]).first()
        if plan is None:
            raise ApiException("Plano no encontrado.", code="not_found", status_code=404)
        assert_can_edit_project(request.user, plan.project)

        # Plan de suscripción: Free solo puede usar el detector mock.
        detector = payload.get("detector")
        if detector and detector not in allowed_detectors(request.user):
            raise ApiException(
                "Ese detector requiere el plan Pro. Tu plan solo permite la detección mock.",
                code="forbidden", status_code=403,
            )

        options = {
            "pixels_per_meter": payload.get("pixels_per_meter"),
            "confidence_threshold": payload.get("confidence_threshold"),
        }
        job = services.run_pipeline(
            plan=plan, detector_name=payload.get("detector"), options=options
        )
        return Response(
            DetectionJobSerializer(job, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["detection"])
class DetectionJobViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Read-only access to the caller's detection jobs."""

    serializer_class = DetectionJobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return DetectionJob.objects.none()
        return DetectionJob.objects.filter(plan__in=plans_for(user))
