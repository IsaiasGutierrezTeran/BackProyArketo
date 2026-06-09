"""Payment gateways behind a single interface (mock by default)."""

from .base import BillingGatewayBase, GatewayResult
from .mock import MockGateway
from .stripe import StripeGateway

__all__ = ["BillingGatewayBase", "GatewayResult", "MockGateway", "StripeGateway"]
