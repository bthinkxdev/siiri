"""Celery tasks for the payments app."""

from __future__ import annotations

from celery import shared_task

from payments.services import recover_stale_razorpay_orders


@shared_task(name="payments.tasks.recover_stale_razorpay_orders")
def recover_stale_razorpay_orders_task() -> int:
    """Beat task: reconcile Razorpay orders the webhook/callback never confirmed."""
    return len(recover_stale_razorpay_orders())
