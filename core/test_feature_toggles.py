"""Feature toggles: OFF features 404 / disappear; ON features behave as before."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.services import register_customer_email
from core.services import get_site_settings


def _set(**flags) -> None:
    site = get_site_settings()
    for key, value in flags.items():
        setattr(site, key, value)
    site.save()


class FeatureToggleTests(TestCase):
    def test_rentals_view_404_off_200_on(self):
        _set(rentals_enabled=False)
        self.assertEqual(self.client.get(reverse("catalog:rental-list")).status_code, 404)
        _set(rentals_enabled=True)
        self.assertEqual(self.client.get(reverse("catalog:rental-list")).status_code, 200)

    def test_subscription_list_404_when_off(self):
        register_customer_email(email="sub@example.com", password="testpass12345", name="Sub")
        self.client.login(username="sub@example.com", password="testpass12345")
        user = User.objects.get(email="sub@example.com")
        self.client.force_login(user)
        _set(subscriptions_enabled=False)
        self.assertEqual(self.client.get(reverse("accounts:subscription-list")).status_code, 404)
        _set(subscriptions_enabled=True)
        self.assertEqual(self.client.get(reverse("accounts:subscription-list")).status_code, 200)

    def test_newsletter_subscribe_404_when_off(self):
        url = reverse("marketing:newsletter-subscribe")
        _set(newsletter_enabled=False)
        self.assertEqual(self.client.post(url, {"email": "a@example.com"}).status_code, 404)
        _set(newsletter_enabled=True)
        self.assertNotEqual(self.client.post(url, {"email": "a@example.com"}).status_code, 404)

    def test_dashboard_sidebar_hides_brands_when_off(self):
        admin = User.objects.create_superuser("dash", "dash@example.com", "testpass12345")
        self.client.force_login(admin)
        url = reverse("dashboard:product-list")
        _set(brands_enabled=False)
        self.assertNotContains(self.client.get(url), reverse("dashboard:brand-list"))
        _set(brands_enabled=True)
        self.assertContains(self.client.get(url), reverse("dashboard:brand-list"))


class DeliveryOffRenderTests(TestCase):
    """Render customer and admin order pages with Delivery Integration ON and OFF."""

    def setUp(self):
        from catalog.models import Product
        from core.models import Currency
        from delhivery.models import DelhiveryShipment
        from orders.models import Order, OrderItem, OrderStatus

        currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="render@example.com", password="testpass12345", name="Render"
        )
        product = Product.objects.create(
            name="Saree", slug="saree", sku="SKU-R1",
            base_price="500.00", mrp="500.00", purchase_price="300.00", stock_quantity=5,
        )
        self.order = Order.objects.create(
            customer_profile=self.profile, order_number="#R-1", idempotency_key="r-1",
            order_status=OrderStatus.READY_TO_SHIP, subtotal="500.00", total_amount="500.00",
            currency=currency,
        )
        OrderItem.objects.create(order=self.order, product=product, quantity=1, unit_price="500.00")
        DelhiveryShipment.objects.create(order=self.order, waybill_number="WB123456")
        self.customer = User.objects.get(email="render@example.com")
        self.staff = User.objects.create_superuser("admin", "admin@example.com", "pw12345678")

    def _customer_pages(self):
        self.client.force_login(self.customer)
        return [
            self.client.get(reverse("orders:detail", args=[self.order.pk])),
            self.client.get(reverse("orders:list")),
        ]

    def test_customer_pages_delivery_on_and_off(self):
        _set(delivery_integration_enabled=True)
        for response in self._customer_pages():
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "delhivery.com")
        _set(delivery_integration_enabled=False)
        for response in self._customer_pages():
            self.assertEqual(response.status_code, 200)
            body = response.content.decode().lower()
            self.assertNotIn("delhivery", body)
            self.assertNotIn("wb123456", body)
            self.assertNotIn("courier tracking", body)

    def test_dashboard_order_detail_delivery_on_and_off(self):
        self.client.force_login(self.staff)
        url = reverse("dashboard:order-detail", args=[self.order.pk])
        _set(delivery_integration_enabled=True)
        on = self.client.get(url)
        self.assertEqual(on.status_code, 200)
        self.assertContains(on, "Update Tracking ID")
        _set(delivery_integration_enabled=False)
        off = self.client.get(url)
        self.assertEqual(off.status_code, 200)
        body = off.content.decode()
        self.assertNotIn("Update Tracking ID", body)
        self.assertNotIn("Delhivery", body)
        self.assertContains(off, "Picked Up")  # manual shipment transition offered

    def test_tracking_update_404_when_off(self):
        self.client.force_login(self.staff)
        url = reverse("dashboard:order-tracking-update", args=[self.order.pk])
        _set(delivery_integration_enabled=False)
        self.assertEqual(self.client.post(url, {"waybill_number": "X"}).status_code, 404)

    def test_delhivery_admin_blocked_when_off(self):
        self.client.force_login(self.staff)
        url = reverse("admin:delhivery_delhiveryshipment_changelist")
        _set(delivery_integration_enabled=True)
        self.assertEqual(self.client.get(url).status_code, 200)
        _set(delivery_integration_enabled=False)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_queued_shipment_task_skips_when_off(self):
        from unittest import mock

        from delhivery.tasks import create_shipment_for_order

        _set(delivery_integration_enabled=False)
        with mock.patch("delhivery.services.trigger_shipment_on_confirmed") as trigger:
            self.assertFalse(create_shipment_for_order(order_id=self.order.pk))
        trigger.assert_not_called()

    def test_brand_preserved_when_brands_off(self):
        from catalog.models import Brand, Product
        from dashboard.forms import ProductForm

        brand = Brand.objects.create(name="B", slug="b")
        product = Product.objects.get(slug="saree")
        product.brand = brand
        product.save()
        _set(brands_enabled=False)
        self.assertNotIn("brand", ProductForm(instance=product).fields)
        _set(brands_enabled=True)
        self.assertIn("brand", ProductForm(instance=product).fields)
