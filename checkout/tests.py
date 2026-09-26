"""Tests for the Razorpay browser-redirect checkout callback."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.services import register_customer_email
from cart.models import Cart, CartItem
from catalog.models import Product
from checkout.services import create_checkout_session, place_order
from core.models import Currency
from orders.models import Order, OrderStatus, OrderStatusHistory
from payments.exceptions import PaymentGatewayError
from payments.models import PaymentStatus, PaymentTransaction


class RazorpayCallbackViewTests(TestCase):
    """
    adapter.capture_payment()'s result must gate confirmation: a valid redirect
    signature only proves the payment *request* was authentic, not that the
    money was actually captured (relevant when auto-capture is off). Confirming
    regardless of the capture result would ship orders that were never paid.
    """

    def setUp(self) -> None:
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="callback-test@example.com",
            password="testpass12345",
            name="Callback Test",
        )
        self.product = Product.objects.create(
            name="Test Yarn",
            slug="test-yarn",
            sku="SKU-TEST-CB-1",
            base_price="500.00",
            mrp="500.00",
            purchase_price="300.00",
            stock_quantity=100,
        )
        self._delhivery_patch = patch("delhivery.tasks.create_shipment_for_order.delay")
        self._delhivery_patch.start()
        self.addCleanup(self._delhivery_patch.stop)

        cart = Cart.objects.create(customer_profile=self.profile, currency=self.currency)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
            unit_price_at_add=self.product.base_price,
        )
        session = create_checkout_session(cart=cart, customer_profile=self.profile)
        self.order = place_order(
            checkout_session_id=session.pk,
            idempotency_key="callback-test-order-1",
            gateway_key="razorpay_upi",
            customer_profile=self.profile,
        )
        self.tx = PaymentTransaction.objects.create(
            order=self.order,
            gateway_key="razorpay_upi",
            amount=self.order.total_amount,
            currency=self.order.currency,
            status=PaymentStatus.PENDING,
            external_intent_id="order_rzp_test_1",
        )
        self.callback_url = reverse("checkout:razorpay-callback")

    @patch("payments.adapters.concrete.RazorpayAdapter.capture_payment", return_value=True)
    @patch("payments.adapters.concrete.RazorpayAdapter.verify_payment_signature", return_value=True)
    def test_valid_signature_and_successful_capture_confirms_order(self, mock_verify, mock_capture):
        response = self.client.post(
            self.callback_url,
            data={
                "order_id": self.order.pk,
                "razorpay_payment_id": "pay_real",
                "razorpay_order_id": "order_rzp_test_1",
                "razorpay_signature": "irrelevant-signature-is-mocked",
            },
        )
        self.order.refresh_from_db()
        self.tx.refresh_from_db()
        self.assertEqual(self.order.order_status, OrderStatus.CONFIRMED)
        self.assertEqual(self.tx.status, PaymentStatus.SUCCESS)
        self.assertEqual(self.tx.external_transaction_id, "pay_real")
        self.assertRedirects(
            response,
            reverse("checkout:confirmation", kwargs={"order_id": self.order.pk}),
            fetch_redirect_response=False,
        )

    @patch("payments.adapters.concrete.RazorpayAdapter.capture_payment", return_value=False)
    @patch("payments.adapters.concrete.RazorpayAdapter.verify_payment_signature", return_value=True)
    def test_valid_signature_but_failed_capture_does_not_confirm_order(self, mock_verify, mock_capture):
        response = self.client.post(
            self.callback_url,
            data={
                "order_id": self.order.pk,
                "razorpay_payment_id": "pay_never_captured",
                "razorpay_order_id": "order_rzp_test_1",
                "razorpay_signature": "irrelevant-signature-is-mocked",
            },
        )
        self.order.refresh_from_db()
        self.tx.refresh_from_db()
        self.assertEqual(self.order.order_status, OrderStatus.CHECKOUT_PENDING)
        self.assertEqual(self.tx.status, PaymentStatus.FAILED)
        self.assertEqual(OrderStatusHistory.objects.filter(order=self.order).count(), 0)
        self.assertRedirects(response, reverse("checkout:checkout"), fetch_redirect_response=False)

    @patch("payments.adapters.concrete.RazorpayAdapter.capture_payment", return_value=True)
    @patch("payments.adapters.concrete.RazorpayAdapter.verify_payment_signature", return_value=True)
    def test_genuine_signature_for_a_different_order_is_rejected(self, mock_verify, mock_capture):
        """
        A cryptographically valid signature only proves Razorpay issued it for
        *some* order — never that it belongs to the order_id in this request.
        Without binding to payment_tx.external_intent_id, a real signature
        obtained by legitimately paying a *different* order could be replayed
        here (with this order's id swapped into the POST body) to confirm this
        order for free. The signature is mocked True to prove the rejection
        happens on the order/intent binding check, before/regardless of
        whatever verify_payment_signature would have said.
        """
        other_tx = PaymentTransaction.objects.create(
            order=self.order,
            gateway_key="razorpay_upi",
            amount=self.order.total_amount,
            currency=self.order.currency,
            status=PaymentStatus.PENDING,
            external_intent_id="order_rzp_attacker_real_order",
        )
        response = self.client.post(
            self.callback_url,
            data={
                "order_id": self.order.pk,
                "razorpay_payment_id": "pay_from_a_different_real_order",
                #this does NOT match self.tx/other_tx's external_intent_id
                "razorpay_order_id": "order_rzp_test_1",
                "razorpay_signature": "a-genuine-signature-for-the-other-order",
            },
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, OrderStatus.CHECKOUT_PENDING)
        mock_capture.assert_not_called()
        self.assertRedirects(response, reverse("checkout:checkout"), fetch_redirect_response=False)


class RazorpayGuestOrderAccessTests(TestCase):
    """
    Order PKs are sequential/guessable — the confirmation and payment pages
    must only be viewable by the session that actually placed the order (or
    its authenticated owner), not by anyone who edits the URL.
    """

    def setUp(self) -> None:
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="idor-owner@example.com", password="testpass12345", name="Owner"
        )
        self.product = Product.objects.create(
            name="Test Yarn", slug="idor-test-yarn", sku="SKU-IDOR-1",
            base_price="500.00", mrp="500.00", purchase_price="300.00", stock_quantity=100,
        )
        cart = Cart.objects.create(customer_profile=self.profile, currency=self.currency)
        CartItem.objects.create(
            cart=cart, product=self.product, quantity=1, unit_price_at_add=self.product.base_price,
        )
        session = create_checkout_session(cart=cart, customer_profile=self.profile)
        self.order = place_order(
            checkout_session_id=session.pk,
            idempotency_key="idor-test-order-1",
            gateway_key="cod",
            customer_profile=self.profile,
        )

    def test_confirmation_page_not_viewable_by_an_unrelated_session(self):
        #a fresh client = a fresh session that never placed this order and is
        #not logged in as its owner.
        from django.test import Client
        stranger = Client()
        response = stranger.get(reverse("checkout:confirmation", kwargs={"order_id": self.order.pk}))
        self.assertEqual(response.status_code, 404)

    def test_confirmation_page_viewable_by_the_authenticated_owner(self):
        self.client.force_login(self.profile.user)
        response = self.client.get(reverse("checkout:confirmation", kwargs={"order_id": self.order.pk}))
        self.assertEqual(response.status_code, 200)

    def test_confirmation_page_viewable_by_the_guest_session_that_placed_it(self):
        #simulate exactly what _grant_order_session_access stores at the
        #moment checkout_place_order_view successfully creates the order.
        session = self.client.session
        session["owned_order_ids"] = [self.order.pk]
        session.save()
        response = self.client.get(reverse("checkout:confirmation", kwargs={"order_id": self.order.pk}))
        self.assertEqual(response.status_code, 200)


class PlaceOrderGatewayUnavailableTests(TestCase):
    """
    If Razorpay is configured but unreachable/rejects the request,
    checkout_place_order_view must render a friendly, actionable error — not
    propagate PaymentGatewayError into an unhandled 500. The order itself
    stays at CHECKOUT_PENDING so the same idempotency_key can be resubmitted
    with Cash on Delivery (see PlaceOrderCodAfterAbandonedOnlineAttemptTests).
    """

    def setUp(self) -> None:
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="gateway-down@example.com", password="testpass12345", name="Gateway Down"
        )
        self.product = Product.objects.create(
            name="Test Yarn", slug="gateway-down-yarn", sku="SKU-GWDOWN-1",
            base_price="500.00", mrp="500.00", purchase_price="300.00", stock_quantity=100,
        )
        self.cart = Cart.objects.create(customer_profile=self.profile, currency=self.currency)
        CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1, unit_price_at_add=self.product.base_price,
        )
        self.client.force_login(self.profile.user)

    @patch(
        "payments.adapters.concrete.RazorpayAdapter.create_payment_intent",
        side_effect=PaymentGatewayError("The payment gateway rejected the order. Please try again."),
    )
    def test_gateway_failure_renders_friendly_error_not_500(self, mock_create_intent):
        response = self.client.post(
            reverse("checkout:place-order"),
            data={
                "gateway_key": "razorpay_upi",
                "idempotency_key": "gateway-down-key-1",
                "guest_name": "Gateway Down",
                "guest_email": "gateway-down@example.com",
                "guest_phone": "9876543210",
                "guest_address_line1": "123 Test Street",
                "guest_city": "Chennai",
                "guest_state": "Tamil Nadu",
                "guest_pincode": "600001",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cash on Delivery")
        from orders.models import Order, OrderStatus
        order = Order.objects.get(idempotency_key="gateway-down-key-1")
        self.assertEqual(order.order_status, OrderStatus.CHECKOUT_PENDING)


class PlaceOrderCodAfterAbandonedOnlineAttemptTests(TestCase):
    """
    A customer who starts checkout with an online gateway (leaving an order
    stuck at CHECKOUT_PENDING when the payment is abandoned), then switches
    to Cash on Delivery and resubmits, must end up with a real PLACED_COD
    order — not one still stuck at CHECKOUT_PENDING, which the admin sees as
    an "abandoned checkout" instead of an order. The checkout form's hidden
    idempotency_key input isn't recomputed when the payment method changes,
    so the COD resubmission commonly arrives with the *same* idempotency_key
    as the earlier abandoned online attempt.
    """

    def setUp(self) -> None:
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="cod-switch-test@example.com",
            password="testpass12345",
            name="Cod Switch Test",
        )
        self.product = Product.objects.create(
            name="Test Yarn",
            slug="test-yarn-cod",
            sku="SKU-TEST-COD-1",
            base_price="500.00",
            mrp="500.00",
            purchase_price="300.00",
            stock_quantity=100,
        )
        self._delhivery_patch = patch("delhivery.tasks.create_shipment_for_order.delay")
        self._delhivery_patch.start()
        self.addCleanup(self._delhivery_patch.stop)

        self.cart = Cart.objects.create(customer_profile=self.profile, currency=self.currency)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=1,
            unit_price_at_add=self.product.base_price,
        )
        self.session = create_checkout_session(cart=self.cart, customer_profile=self.profile)

    def test_cod_resubmission_with_stale_idempotency_key_converts_pending_order(self):
        idempotency_key = f"{self.session.pk}-stale-key-from-first-page-load"

        abandoned_order = place_order(
            checkout_session_id=self.session.pk,
            idempotency_key=idempotency_key,
            gateway_key="razorpay_upi",
            customer_profile=self.profile,
        )
        self.assertEqual(abandoned_order.order_status, OrderStatus.CHECKOUT_PENDING)

        self.session.refresh_from_db()

        cod_order = place_order(
            checkout_session_id=self.session.pk,
            idempotency_key=idempotency_key,
            gateway_key="cod",
            customer_profile=self.profile,
        )

        self.assertEqual(cod_order.pk, abandoned_order.pk)
        self.assertEqual(cod_order.order_status, OrderStatus.PLACED_COD)
        self.assertEqual(Order.objects.filter(cart=self.cart).count(), 1)

    def test_duplicate_cod_conversion_call_does_not_create_second_order(self):
        """
        Simulates a duplicate place_order call landing after the first one
        already converted an abandoned online order to COD, but before
        confirm_payment_success has flipped the session to COMPLETED (the
        window process_payment/confirm_payment_success runs in, outside
        place_order's transaction). The duplicate must return the same order,
        not fall through and create a second one with a second stock decrement.
        """
        idempotency_key_1 = f"{self.session.pk}-first-attempt-key"
        abandoned_order = place_order(
            checkout_session_id=self.session.pk,
            idempotency_key=idempotency_key_1,
            gateway_key="razorpay_upi",
            customer_profile=self.profile,
        )
        self.session.refresh_from_db()

        idempotency_key_2 = f"{self.session.pk}-cod-attempt-key"
        first_cod_call = place_order(
            checkout_session_id=self.session.pk,
            idempotency_key=idempotency_key_2,
            gateway_key="cod",
            customer_profile=self.profile,
        )
        self.assertEqual(first_cod_call.pk, abandoned_order.pk)
        self.assertEqual(first_cod_call.order_status, OrderStatus.PLACED_COD)

        #session.status is still DRAFT here — confirm_payment_success (which
        #flips it to COMPLETED) hasn't run yet, matching the real race window.
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "draft")

        duplicate_call = place_order(
            checkout_session_id=self.session.pk,
            idempotency_key=idempotency_key_2,
            gateway_key="cod",
            customer_profile=self.profile,
        )

        self.assertEqual(duplicate_call.pk, abandoned_order.pk)
        self.assertEqual(Order.objects.filter(cart=self.cart).count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 99)
