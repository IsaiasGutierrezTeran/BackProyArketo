"""Budget endpoints: materials catalog (superadmin) + budgets + engineer review."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsSuperAdmin

from . import services
from .models import Material, MaterialCategory
from .serializers import (
    BudgetCreateSerializer,
    BudgetReviewInputSerializer,
    BudgetSerializer,
    MaterialCategorySerializer,
    MaterialSerializer,
)


class _ReadAnyWriteSuperAdmin(viewsets.ModelViewSet):
    """Authenticated users read the catalog; only superadmin can modify it."""

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]


@extend_schema(tags=["budget"])
class MaterialCategoryViewSet(_ReadAnyWriteSuperAdmin):
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer


@extend_schema(tags=["budget"])
class MaterialViewSet(_ReadAnyWriteSuperAdmin):
    queryset = Material.objects.select_related("category").all()
    serializer_class = MaterialSerializer


@extend_schema(tags=["budget"])
class BudgetViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Create/list budgets scoped to the user's projects; submit + engineer review."""

    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not user.is_authenticated:
            return services.budgets_for(user).none()
        qs = services.budgets_for(user)
        project = self.request.query_params.get("project")
        return qs.filter(project=project) if project else qs

    @extend_schema(request=BudgetCreateSerializer, responses={201: BudgetSerializer},
                   summary="Crear presupuesto (calcula subtotales y total)")
    def create(self, request):
        data = BudgetCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        budget = services.create_budget(
            user=request.user,
            project_id=data.validated_data["project"],
            items=data.validated_data["items"],
            labor_people=data.validated_data["labor_people"],
            labor_cost=data.validated_data["labor_cost"],
            currency=data.validated_data.get("currency"),
        )
        return Response(
            BudgetSerializer(budget, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: BudgetSerializer},
                   summary="Enviar el presupuesto a revisión")
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        budget = services.submit_budget(user=request.user, budget=self.get_object())
        return Response(BudgetSerializer(budget, context={"request": request}).data)

    def perform_destroy(self, instance):
        services.delete_budget(user=self.request.user, budget=instance)

    @extend_schema(request=BudgetReviewInputSerializer, responses={200: BudgetSerializer},
                   summary="Revisión del Ingeniero (aprobar/observar/rechazar)")
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        data = BudgetReviewInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        budget = services.review_budget(
            budget=self.get_object(),
            reviewer=request.user,
            decision=data.validated_data["decision"],
            comments=data.validated_data.get("comments", ""),
        )
        return Response(BudgetSerializer(budget, context={"request": request}).data)
