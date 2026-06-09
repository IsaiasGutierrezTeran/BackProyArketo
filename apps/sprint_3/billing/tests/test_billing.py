"""CU17 — plans catalog (superadmin write) + subscribe/cancel via mock gateway."""

from __future__ import annotations

from decimal import Decimal

import pytest

from accounts.models import Role
from billing.models import SubscriptionPlan

pytestmark = pytest.mark.django_db


def test_plan_write_requires_superadmin(make_user, auth_client):
    payload = {"code": "x", "name": "X", "price": "5.00", "interval": "month"}
    cliente = auth_client(make_user(role=Role.CLIENTE))
    assert cliente.post("/api/billing/plans/", payload, format="json").status_code == 403

    admin = auth_client(make_user(email="s@x.dev", role=Role.SUPERADMIN))
    assert admin.post("/api/billing/plans/", payload, format="json").status_code == 201


def test_subscribe_mock_activates_then_cancel(make_user, auth_client):
    SubscriptionPlan.objects.create(code="pro", name="Pro", price=Decimal("19.00"))
    user = make_user()
    client = auth_client(user)

    subscribed = client.post("/api/billing/subscribe", {"plan": "pro"}, format="json")
    assert subscribed.status_code == 200
    data = subscribed.json()["data"]
    assert data["status"] == "active"
    assert data["checkout_url"] is None  # mock gateway, no off-site payment
    user.refresh_from_db()
    assert user.subscription_plan == "pro"

    canceled = client.post("/api/billing/cancel")
    assert canceled.status_code == 200
    assert canceled.json()["data"]["status"] == "canceled"
