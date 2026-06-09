"""Payment gateway interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GatewayResult:
    """Outcome of a gateway call.

    `status` is a SubscriptionStatus value. `checkout_url` is set when the user
    must complete payment off-site (real Stripe); it is None for the mock gateway.
    """

    status: str
    checkout_url: str | None = None
    customer_id: str = ""
    subscription_id: str = ""


class BillingGatewayBase(ABC):
    name: str = "base"

    @abstractmethod
    def start_subscription(self, *, user, plan) -> GatewayResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_subscription(self, *, subscription) -> GatewayResult:
        raise NotImplementedError
