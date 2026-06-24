"""Billing routes, mounted under /api/ -> /api/billing/."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CancelSubscriptionView,
    MySubscriptionView,
    StripeWebhookView,
    SubscribeView,
    SubscriptionPlanViewSet,
)

router = DefaultRouter()
router.register(
    "billing/plans", SubscriptionPlanViewSet, basename="billing-plan"
)

urlpatterns = [
    path(
        "billing/subscription",
        MySubscriptionView.as_view(),
        name="billing-subscription",
    ),
    path(
        "billing/subscribe", SubscribeView.as_view(), name="billing-subscribe"
    ),
    path(
        "billing/cancel",
        CancelSubscriptionView.as_view(),
        name="billing-cancel",
    ),
    path(
        "billing/webhook", StripeWebhookView.as_view(), name="billing-webhook"
    ),
    *router.urls,
]
