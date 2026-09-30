"""Tests for the catalog app."""

from __future__ import annotations

import json

from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from accounts.services import register_customer_email
from catalog.models import Product, ProductVariant
from core.models import Currency
from orders.models import Order, OrderItem, OrderStatus


class ProductDisplayVariantTests(TestCase):
    """Product.display_variant drives storefront price/stock display and (via
    dashboard.views.catalog._render_product_form) the admin's product-level
    price/stock sync — both must agree on which variant is authoritative."""

    def setUp(self) -> None:
        self.product = Product.objects.create(
            name="Variant Yarn",
            slug="variant-yarn",
            sku="SKU-VARIANT-1",
            base_price="100.00",
            mrp="100.00",
            purchase_price="60.00",
        )

    def test_display_variant_prefers_is_default_over_first_in_stock(self) -> None:
        default_but_out_of_stock = ProductVariant.objects.create(
            product=self.product, variant_type="Size", name="S",
            base_price="90.00", mrp="90.00", purchase_price="50.00",
            stock_quantity=0, is_default=True,
        )
        ProductVariant.objects.create(
            product=self.product, variant_type="Size", name="M",
            base_price="110.00", mrp="110.00", purchase_price="70.00",
            stock_quantity=5, is_default=False,
        )
        self.assertEqual(self.product.display_variant.pk, default_but_out_of_stock.pk)

    def test_display_variant_falls_back_to_first_in_stock_when_no_default(self) -> None:
        ProductVariant.objects.create(
            product=self.product, variant_type="Size", name="S",
            base_price="90.00", mrp="90.00", purchase_price="50.00",
            stock_quantity=0,
        )
        in_stock = ProductVariant.objects.create(
            product=self.product, variant_type="Size", name="M",
            base_price="110.00", mrp="110.00", purchase_price="70.00",
            stock_quantity=5,
        )
        self.assertEqual(self.product.display_variant.pk, in_stock.pk)


class ProductVariantDeleteProtectionTests(TestCase):
    """A variant referenced by an existing OrderItem must not be deletable —
    OrderItem.variant is PROTECT (not SET_NULL) precisely so historical order
    data can't silently go missing."""

    def setUp(self) -> None:
        self.product = Product.objects.create(
            name="Protect Yarn",
            slug="protect-yarn",
            sku="SKU-PROTECT-1",
            base_price="100.00",
            mrp="100.00",
            purchase_price="60.00",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, variant_type="Size", name="S",
            base_price="90.00", mrp="90.00", purchase_price="50.00",
            stock_quantity=5,
        )
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="protect-test@example.com", password="testpass12345", name="Protect Test"
        )
        order = Order.objects.create(
            customer_profile=self.profile,
            order_number="#PROTECT-1",
            idempotency_key="protect-1",
            order_status=OrderStatus.PLACED_COD,
            subtotal="90.00",
            total_amount="90.00",
            currency=self.currency,
        )
        OrderItem.objects.create(
            order=order, product=self.product, variant=self.variant,
            variant_name=self.variant.name, variant_sku="SKU-PROTECT-1",
            quantity=1, unit_price="90.00",
        )

    def test_deleting_variant_referenced_by_order_raises_protected_error(self) -> None:
        with self.assertRaises(ProtectedError):
            self.variant.delete()


class MultiVariantTypeGroupingTests(TestCase):
    """SIRI-HOM-005: a product with more than one variant_type (e.g. Size AND Qty)
    must show every group, not just the first one — both the PDP page and the
    homepage Spotlight section regroup variant_list by variant_type."""

    def setUp(self) -> None:
        self.product = Product.objects.create(
            name="Multi Variant Saree",
            slug="multi-variant-saree",
            sku="SKU-MULTI-1",
            base_price="1000.00",
            mrp="1200.00",
            purchase_price="600.00",
            is_active=True,
        )
        ProductVariant.objects.create(
            product=self.product, variant_type="Size", name="S",
            base_price="1000.00", mrp="1200.00", purchase_price="600.00",
            stock_quantity=5, is_default=True,
        )
        ProductVariant.objects.create(
            product=self.product, variant_type="Size", name="M",
            base_price="1000.00", mrp="1200.00", purchase_price="600.00",
            stock_quantity=5,
        )
        ProductVariant.objects.create(
            product=self.product, variant_type="Qty", name="1 Pc",
            base_price="1000.00", mrp="1200.00", purchase_price="600.00",
            stock_quantity=5,
        )
        ProductVariant.objects.create(
            product=self.product, variant_type="Qty", name="2 Pc",
            base_price="1900.00", mrp="2200.00", purchase_price="1100.00",
            stock_quantity=5,
        )

    def test_quick_view_variants_json_includes_type_per_variant(self) -> None:
        data = json.loads(self.product.quick_view_variants_json)
        by_name = {item["name"]: item["type"] for item in data}
        self.assertEqual(by_name["S"], "Size")
        self.assertEqual(by_name["M"], "Size")
        self.assertEqual(by_name["1 Pc"], "Qty")
        self.assertEqual(by_name["2 Pc"], "Qty")

    def test_pdp_renders_both_variant_type_groups(self) -> None:
        response = self.client.get(reverse("catalog:pdp", kwargs={"slug": self.product.slug}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Size", content)
        self.assertIn("Qty", content)
        for variant_name in ("S", "M", "1 Pc", "2 Pc"):
            self.assertIn(variant_name, content)


class PdpVariantSkuTests(TestCase):
    """The PDP SKU must be the selected variant's own SKU (not the parent's, not parent + variant)."""

    def setUp(self) -> None:
        from catalog.models import Product, ProductVariant

        self.product = Product.objects.create(
            name="Sku Kurta", slug="sku-kurta", sku="KRT", base_price="349.00",
            mrp="349.00", purchase_price="100.00", stock_quantity=10,
        )
        mk = lambda name, suffix, default=False: ProductVariant.objects.create(
            product=self.product, variant_type="Size", name=name, base_price="349.00", mrp="349.00",
            purchase_price="100.00", stock_quantity=5, sku_suffix=suffix, is_default=default,
        )
        self.s = mk("S", "S", default=True)
        self.m = mk("M", "M")
        self.plain = mk("L", "")

    def test_variant_price_endpoint_returns_variant_sku(self):
        from django.urls import reverse
        url = reverse("catalog:variant-price", kwargs={"product_id": self.product.pk})
        self.assertEqual(self.client.get(url, {"variant_id": self.m.pk}).json()["sku"], "M")
        self.assertEqual(self.client.get(url, {"variant_id": self.plain.pk}).json()["sku"], "KRT")  #no suffix

    def test_pdp_renders_selected_variant_sku(self):
        from django.urls import reverse
        html = self.client.get(reverse("catalog:pdp", kwargs={"slug": self.product.slug}), {"variant_id": self.m.pk}).content.decode()
        self.assertIn('<span id="pdp-sku-value">M</span>', html)
