"""Domain exceptions for the payments app."""

from __future__ import annotations


class PaymentGatewayError(Exception):
    """Raised when a configured payment gateway can't be reached or rejects a request."""
