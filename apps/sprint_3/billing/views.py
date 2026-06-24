"""Billing endpoints (CU17): plans catalog, subscribe/cancel, current subscription."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsSuperAdmin

from . import services
from .models import SubscriptionPlan
from .serializers import (
    SubscribeSerializer,
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
)


@extend_schema(tags=["billing"])
class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """Plans catalog: any authenticated user reads; only superadmin writes."""

    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]


@extend_schema(tags=["billing"])
class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: SubscriptionSerializer},
        summary="Mi suscripción actual",
    )
    def get(self, request):
        subscription = services.get_subscription(request.user)
        return Response(SubscriptionSerializer(subscription).data)


@extend_schema(tags=["billing"])
class SubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SubscribeSerializer,
        responses={200: SubscriptionSerializer},
        summary="Suscribirse / cambiar de plan",
    )
    def post(self, request):
        data = SubscribeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        subscription, checkout_url = services.subscribe(
            user=request.user, plan_code=data.validated_data["plan"]
        )
        body = SubscriptionSerializer(subscription).data
        body["checkout_url"] = checkout_url  # null for the mock gateway
        return Response(body)


@extend_schema(tags=["billing"])
class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: SubscriptionSerializer},
        summary="Cancelar la suscripción",
    )
    def post(self, request):
        subscription = services.cancel(user=request.user)
        return Response(SubscriptionSerializer(subscription).data)


@extend_schema(tags=["billing"])
class StripeWebhookView(APIView):
    """Stripe webhook receiver: verifies the signature and activates subscriptions.

    Public endpoint (Stripe is not authenticated by JWT); security comes from the
    HMAC-SHA256 signature check against STRIPE_WEBHOOK_SECRET.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        request=None, responses={200: dict}, summary="Webhook de Stripe"
    )
    def post(self, request):
        # Use the raw body for signature verification (do NOT touch request.data).
        event = services.process_stripe_webhook(
            payload=request.body,
            signature=request.META.get("HTTP_STRIPE_SIGNATURE", ""),
        )
        return Response({"received": True, "type": event.get("type", "")})
