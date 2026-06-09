"""Business logic for billing (views only orchestrate)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone as dt_timezone

from django.conf import settings

from core.exceptions import ApiException

from .gateways import MockGateway, StripeGateway
from .gateways.base import BillingGatewayBase
from .models import Subscription, SubscriptionPlan, SubscriptionStatus

_GATEWAYS: dict[str, type[BillingGatewayBase]] = {
    "mock": MockGateway,
    "stripe": StripeGateway,
}


def get_gateway() -> BillingGatewayBase:
    cls = _GATEWAYS.get(settings.BILLING_GATEWAY, MockGateway)
    return cls()


def get_subscription(user) -> Subscription:
    subscription, _ = Subscription.objects.get_or_create(user=user)
    return subscription


def subscribe(*, user, plan_code: str) -> tuple[Subscription, str | None]:
    """Start (or change) a subscription. Returns (subscription, checkout_url)."""
    plan = SubscriptionPlan.objects.filter(code=plan_code, is_active=True).first()
    if plan is None:
        raise ApiException("Plan no encontrado o inactivo.", code="not_found", status_code=404)

    gateway = get_gateway()
    result = gateway.start_subscription(user=user, plan=plan)

    subscription = get_subscription(user)
    subscription.plan = plan
    subscription.status = result.status
    if result.customer_id:
        subscription.stripe_customer_id = result.customer_id
    if result.subscription_id:
        subscription.stripe_subscription_id = result.subscription_id
    subscription.save()

    # Reflect the plan on the user only once the subscription is active.
    if result.status == SubscriptionStatus.ACTIVE:
        user.subscription_plan = plan.code
        user.save(update_fields=["subscription_plan"])

    return subscription, result.checkout_url


def cancel(*, user) -> Subscription:
    subscription = get_subscription(user)
    get_gateway().cancel_subscription(subscription=subscription)
    subscription.status = SubscriptionStatus.CANCELED
    subscription.save(update_fields=["status", "updated_at"])
    user.subscription_plan = "free"
    user.save(update_fields=["subscription_plan"])
    return subscription


# --- Stripe webhook ---------------------------------------------------------
# Signature verification implemented per Stripe's scheme (t=...,v1=...) with
# HMAC-SHA256 so the `stripe` SDK is not required (matches StripeGateway, which
# also uses plain HTTP). Never process an unverified webhook.

def _verify_stripe_signature(payload: bytes, sig_header: str, tolerance: int = 300) -> dict:
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret:
        raise ApiException(
            "STRIPE_WEBHOOK_SECRET no configurada.", code="bad_request", status_code=400
        )
    if not sig_header:
        raise ApiException(
            "Falta la cabecera Stripe-Signature.", code="bad_request", status_code=400
        )

    parts: dict[str, str] = {}
    for item in sig_header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts.setdefault(key.strip(), value.strip())
    timestamp, signature = parts.get("t"), parts.get("v1")
    if not timestamp or not signature:
        raise ApiException("Firma Stripe inválida.", code="bad_request", status_code=400)

    signed_payload = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ApiException("Firma de webhook inválida.", code="bad_request", status_code=400)

    try:
        if abs(time.time() - int(timestamp)) > tolerance:
            raise ApiException(
                "Webhook fuera de la ventana temporal.", code="bad_request", status_code=400
            )
    except ValueError as exc:
        raise ApiException(
            "Timestamp de webhook inválido.", code="bad_request", status_code=400
        ) from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ApiException(
            "Payload de webhook inválido.", code="bad_request", status_code=400
        ) from exc


def _apply_plan_to_user(subscription: Subscription) -> None:
    if subscription.user_id and subscription.plan_id:
        subscription.user.subscription_plan = subscription.plan.code
        subscription.user.save(update_fields=["subscription_plan"])


def process_stripe_webhook(*, payload: bytes, signature: str) -> dict:
    """Verify the signature and apply the event to the local subscription state."""
    event = _verify_stripe_signature(payload, signature)
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        subscription = Subscription.objects.filter(
            user_id=obj.get("client_reference_id")
        ).first()
        if subscription is not None:
            subscription.status = SubscriptionStatus.ACTIVE
            if obj.get("subscription"):
                subscription.stripe_subscription_id = obj["subscription"]
            if obj.get("customer"):
                subscription.stripe_customer_id = obj["customer"]
            subscription.save()
            _apply_plan_to_user(subscription)

    elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
        subscription = Subscription.objects.filter(
            stripe_subscription_id=obj.get("id", "")
        ).first()
        if subscription is not None:
            canceled = event_type.endswith("deleted") or obj.get("status") == "canceled"
            if canceled:
                subscription.status = SubscriptionStatus.CANCELED
                if subscription.user_id:
                    subscription.user.subscription_plan = "free"
                    subscription.user.save(update_fields=["subscription_plan"])
            else:
                status_map = {
                    "active": SubscriptionStatus.ACTIVE,
                    "past_due": SubscriptionStatus.PAST_DUE,
                    "incomplete": SubscriptionStatus.INCOMPLETE,
                }
                subscription.status = status_map.get(obj.get("status", ""), subscription.status)
            period_end = obj.get("current_period_end")
            if period_end:
                subscription.current_period_end = datetime.fromtimestamp(
                    int(period_end), tz=dt_timezone.utc
                )
            subscription.save()
            if subscription.status == SubscriptionStatus.ACTIVE:
                _apply_plan_to_user(subscription)

    return event
