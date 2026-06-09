"""Mock gateway: activates subscriptions immediately (no real payment)."""

from __future__ import annotations

from .base import BillingGatewayBase, GatewayResult


class MockGateway(BillingGatewayBase):
    name = "mock"

    def start_subscription(self, *, user, plan) -> GatewayResult:
        return GatewayResult(
            status="active",
            checkout_url=None,
            customer_id=f"mock_cus_{user.id}",
            subscription_id=f"mock_sub_{user.id}_{plan.code}",
        )

    def cancel_subscription(self, *, subscription) -> GatewayResult:
        return GatewayResult(status="canceled")
