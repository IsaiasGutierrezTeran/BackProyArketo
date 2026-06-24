"""Stripe gateway (opt-in via BILLING_GATEWAY=stripe + STRIPE_SECRET_KEY).

Implemented with plain HTTP so the `stripe` SDK is not a hard dependency. Creates
a Checkout Session; the subscription is activated by the webhook on payment.
"""

from __future__ import annotations

import requests
from django.conf import settings

from core.exceptions import ApiException

from .base import BillingGatewayBase, GatewayResult

_CHECKOUT_URL = "https://api.stripe.com/v1/checkout/sessions"


class StripeGateway(BillingGatewayBase):
    name = "stripe"

    def _key(self) -> str:
        if not settings.STRIPE_SECRET_KEY:
            raise ApiException(
                "STRIPE_SECRET_KEY no configurada.",
                code="bad_request",
                status_code=400,
            )
        return settings.STRIPE_SECRET_KEY

    def start_subscription(self, *, user, plan) -> GatewayResult:
        if not plan.stripe_price_id:
            raise ApiException(
                f"El plan '{plan.code}' no tiene stripe_price_id.",
                code="bad_request",
            )
        data = {
            "mode": "subscription",
            "success_url": settings.BILLING_SUCCESS_URL,
            "cancel_url": settings.BILLING_CANCEL_URL,
            "client_reference_id": str(user.id),
            "line_items[0][price]": plan.stripe_price_id,
            "line_items[0][quantity]": "1",
        }
        try:
            resp = requests.post(
                _CHECKOUT_URL, data=data, auth=(self._key(), ""), timeout=30
            )
        except requests.RequestException as exc:
            raise ApiException(
                "No se pudo contactar Stripe.",
                code="inference_error",
                status_code=502,
            ) from exc
        if resp.status_code >= 400:
            raise ApiException(
                f"Stripe respondió {resp.status_code}.",
                code="inference_error",
                status_code=502,
            )
        session = resp.json()
        # Payment pending until the webhook confirms it.
        return GatewayResult(
            status="incomplete",
            checkout_url=session.get("url"),
            customer_id=session.get("customer", "") or "",
        )

    def cancel_subscription(self, *, subscription) -> GatewayResult:
        sub_id = subscription.stripe_subscription_id
        if sub_id:
            try:
                requests.delete(
                    f"https://api.stripe.com/v1/subscriptions/{sub_id}",
                    auth=(self._key(), ""),
                    timeout=30,
                )
            except requests.RequestException:
                pass
        return GatewayResult(status="canceled")
