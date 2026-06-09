"""Subscription plans and per-user subscriptions."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import BaseModel


class BillingInterval(models.TextChoices):
    MONTH = "month", "Mensual"
    YEAR = "year", "Anual"


class SubscriptionPlan(BaseModel):
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    interval = models.CharField(
        max_length=8, choices=BillingInterval.choices, default=BillingInterval.MONTH
    )
    features = models.JSONField(default=list, blank=True)
    stripe_price_id = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        ordering = ["price"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Activa"
    INCOMPLETE = "incomplete", "Pendiente de pago"
    PAST_DUE = "past_due", "Vencida"
    CANCELED = "canceled", "Cancelada"


class Subscription(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, related_name="subscriptions"
    )
    status = models.CharField(
        max_length=12, choices=SubscriptionStatus.choices, default=SubscriptionStatus.INCOMPLETE
    )
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Subscription({self.user_id}, {self.status})"
