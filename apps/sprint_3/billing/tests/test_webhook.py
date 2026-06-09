"""HU-17 — Stripe webhook: signature verification + subscription activation."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from billing.models import Subscription, SubscriptionPlan

pytestmark = pytest.mark.django_db

_SECRET = "whsec_test_secret"


def _sign(payload: bytes, secret: str = _SECRET) -> str:
    # Stripe signs `f"{t}.{payload}"` with HMAC-SHA256; mirror the service.
    t = int(time.time())
    signed = f"{t}.".encode() + payload
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={t},v1={signature}"


def test_webhook_activates_subscription(settings, make_user):
    settings.STRIPE_WEBHOOK_SECRET = _SECRET
    plan = SubscriptionPlan.objects.create(code="pro", name="Pro", price=Decimal("19"))
    user = make_user()
    Subscription.objects.create(user=user, plan=plan, status="incomplete")

    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {
            "client_reference_id": str(user.id),
            "subscription": "sub_123",
            "customer": "cus_123",
        }},
    }).encode()

    resp = APIClient().post(
        "/api/billing/webhook", data=payload, content_type="application/json",
        HTTP_STRIPE_SIGNATURE=_sign(payload),
    )

    assert resp.status_code == 200
    sub = Subscription.objects.get(user=user)
    assert sub.status == "active"
    assert sub.stripe_subscription_id == "sub_123"
    user.refresh_from_db()
    assert user.subscription_plan == "pro"


def test_webhook_rejects_bad_signature(settings):
    settings.STRIPE_WEBHOOK_SECRET = _SECRET
    resp = APIClient().post(
        "/api/billing/webhook", data=b"{}", content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=deadbeef",
    )
    assert resp.status_code == 400
