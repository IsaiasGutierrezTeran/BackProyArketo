"""Serializers (I/O only) for billing."""

from __future__ import annotations

from rest_framework import serializers

from .models import Subscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "code",
            "name",
            "price",
            "interval",
            "features",
            "stripe_price_id",
            "is_active",
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "plan_code",
            "status",
            "current_period_end",
            "updated_at",
        ]
        read_only_fields = fields


class SubscribeSerializer(serializers.Serializer):
    plan = serializers.CharField(help_text="Código del plan, p. ej. 'pro'.")
