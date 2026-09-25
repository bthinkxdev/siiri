"""Tests for the Delivery Integration ON/OFF switch."""

from __future__ import annotations

import json
from unittest import mock

from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from core.features import feature_required, is_enabled
from core.services import get_site_settings
from delhivery.views import delhivery_webhook
from orders.models import OrderStatus
from orders.services import ALLOWED_STATUS_TRANSITIONS, allowed_next_statuses


def _set_delivery(enabled: bool) -> None:
    settings_row = get_site_settings()
    settings_row.delivery_integration_enabled = enabled
    settings_row.save()


class DeliverySwitchTests(TestCase):
    def test_default_is_on(self) -> None:
        self.assertTrue(is_enabled("delivery_integration"))

    def test_optional_feature_defaults(self) -> None:
        row = get_site_settings()
        self.assertFalse(row.brands_enabled)
        self.assertFalse(row.subscriptions_enabled)
        self.assertFalse(row.rentals_enabled)
        self.assertFalse(row.gift_builder_enabled)
        self.assertTrue(row.newsletter_enabled)

    def test_transitions_unchanged_when_on(self) -> None:
        for status in OrderStatus.values:
            self.assertEqual(
                allowed_next_statuses(status), ALLOWED_STATUS_TRANSITIONS.get(status, set())
            )

    def test_manual_shipment_transitions_when_off(self) -> None:
        _set_delivery(False)
        self.assertIn(OrderStatus.PICKED_UP, allowed_next_statuses(OrderStatus.READY_TO_SHIP))
        self.assertEqual(
            allowed_next_statuses(OrderStatus.OUT_FOR_DELIVERY), {OrderStatus.DELIVERED}
        )
        # non-shipment rules are unchanged
        self.assertEqual(
            allowed_next_statuses(OrderStatus.CONFIRMED),
            ALLOWED_STATUS_TRANSITIONS[OrderStatus.CONFIRMED],
        )

    @override_settings(DELHIVERY_WEBHOOK_TOKEN="tok")
    def test_webhook_ignored_when_off(self) -> None:
        _set_delivery(False)
        request = RequestFactory().post(
            "/delhivery/webhook/",
            data=json.dumps({"waybill": "123", "status": "delivered"}),
            content_type="application/json",
            HTTP_X_DELHIVERY_TOKEN="tok",
        )
        with mock.patch("delhivery.views.transition_order_status") as transition:
            response = delhivery_webhook(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["status"], "ignored")
        transition.assert_not_called()

    @override_settings(DELHIVERY_WEBHOOK_TOKEN="tok")
    def test_webhook_still_requires_token_when_off(self) -> None:
        _set_delivery(False)
        request = RequestFactory().post(
            "/delhivery/webhook/", data="{}", content_type="application/json"
        )
        self.assertEqual(delhivery_webhook(request).status_code, 401)

    def test_feature_required_decorator(self) -> None:
        @feature_required("brands")
        def view(request):
            return "ok"

        request = RequestFactory().get("/")
        with self.assertRaises(Http404):
            view(request)
        row = get_site_settings()
        row.brands_enabled = True
        row.save()
        self.assertEqual(view(request), "ok")

    def test_shipment_hook_gated(self) -> None:
        from orders.plugins import order_confirmed_registry

        order = mock.Mock(pk=1)
        with mock.patch("delhivery.tasks.create_shipment_for_order.delay") as delay:
            _set_delivery(False)
            order_confirmed_registry.execute_plugins(order)
            delay.assert_not_called()
            _set_delivery(True)
            order_confirmed_registry.execute_plugins(order)
            delay.assert_called_once_with(order_id=1)
