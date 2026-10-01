"""Tests for the dashboard app.

Access control, CRUD flows, and report views are exercised here. Add cases
under a tests/ package as coverage grows (see scripts/scaffold_apps.py).
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.services import register_customer_email
from cart.models import Cart, CartItem
from catalog.models import Product
from checkout.services import create_checkout_session, place_order
from core.models import Currency
from dashboard.forms import ProductVariantForm, ProductVariantFormSet
from orders.models import Order, OrderStatus
from payments.models import PaymentStatus, PaymentTransaction
from payments.services import confirm_payment_success


class OrderListTabsTests(TestCase):
    """The Orders list splits real orders from CHECKOUT_PENDING abandoned
    checkouts into two tabs (see dashboard/views/orders.py::order_list)."""

    def setUp(self) -> None:
        self.staff_user = User.objects.create_superuser(
            username="dash-admin", email="dash-admin@example.com", password="testpass12345"
        )
        self.client.force_login(self.staff_user)

        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="dash-order-test@example.com", password="testpass12345", name="Dash Order Test"
        )
        self.product = Product.objects.create(
            name="Test Yarn",
            slug="dash-test-yarn",
            sku="SKU-DASH-1",
            base_price="500.00",
            mrp="500.00",
            purchase_price="300.00",
            stock_quantity=100,
        )

        self.confirmed_order = self._place_order("confirmed")
        tx = PaymentTransaction.objects.create(
            order=self.confirmed_order,
            gateway_key="razorpay_upi",
            amount=self.confirmed_order.total_amount,
            currency=self.confirmed_order.currency,
            status=PaymentStatus.PENDING,
            external_intent_id="order_dash_confirmed_1",
        )
        confirm_payment_success(payment_transaction=tx, external_transaction_id="pay_dash_confirmed_1")

        self.abandoned_order = self._place_order("abandoned")
        self.assertEqual(self.abandoned_order.order_status, OrderStatus.CHECKOUT_PENDING)

    def _place_order(self, suffix: str):
        cart = Cart.objects.create(customer_profile=self.profile, currency=self.currency)
        CartItem.objects.create(
            cart=cart, product=self.product, quantity=1, unit_price_at_add=self.product.base_price
        )
        session = create_checkout_session(cart=cart, customer_profile=self.profile)
        return place_order(
            checkout_session_id=session.pk,
            idempotency_key=f"dash-order-test-{suffix}",
            gateway_key="razorpay_upi",
            customer_profile=self.profile,
        )

    def test_orders_tab_excludes_abandoned_checkouts(self):
        response = self.client.get(reverse("dashboard:order-list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        self.assertContains(response, self.confirmed_order.order_number)
        self.assertNotContains(response, self.abandoned_order.order_number)
        self.assertIn("Abandoned Checkouts", content)
        self.assertIn(">1<", content)  # abandoned_count badge
        self.assertNotIn("Payment Pending", content)  # excluded from status dropdown + rows

    def test_abandoned_tab_shows_only_abandoned_checkouts(self):
        response = self.client.get(reverse("dashboard:order-list") + "?view=abandoned")
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, self.abandoned_order.order_number)
        self.assertNotContains(response, self.confirmed_order.order_number)
        # status dropdown is hidden entirely on this tab
        self.assertNotContains(response, "All order statuses")

    def test_search_filter_works_within_abandoned_tab(self):
        response = self.client.get(
            reverse("dashboard:order-list") + f"?view=abandoned&q={self.abandoned_order.order_number}"
        )
        self.assertContains(response, self.abandoned_order.order_number)

        response = self.client.get(reverse("dashboard:order-list") + "?view=abandoned&q=NO_SUCH_ORDER")
        self.assertNotContains(response, self.abandoned_order.order_number)


class OrderAddressUpdateViewTests(TestCase):
    """dashboard:order-address-update — the previously-missing address edit."""

    def setUp(self) -> None:
        self.staff_user = User.objects.create_superuser(
            username="dash-admin-addr", email="dash-admin-addr@example.com", password="testpass12345"
        )
        self.client.force_login(self.staff_user)

        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.profile = register_customer_email(
            email="dash-addr-test@example.com", password="testpass12345", name="Dash Addr Test"
        )
        self.editable_order = Order.objects.create(
            customer_profile=self.profile,
            order_number="#ADDR-EDITABLE",
            idempotency_key="addr-editable",
            order_status=OrderStatus.PLACED_COD,
            total_amount="500.00",
            currency=self.currency,
            delivery_address_snapshot={
                "name": "Original Name", "line1": "Old Line 1", "city": "Old City",
                "state": "Old State", "pincode": "111111",
            },
        )
        self.delivered_order = Order.objects.create(
            customer_profile=self.profile,
            order_number="#ADDR-DELIVERED",
            idempotency_key="addr-delivered",
            order_status=OrderStatus.DELIVERED,
            total_amount="500.00",
            currency=self.currency,
            delivery_address_snapshot={"name": "Frozen Name", "line1": "Frozen Line 1", "city": "Frozen City"},
        )

    def test_editable_status_updates_snapshot(self) -> None:
        response = self.client.post(
            reverse("dashboard:order-address-update", args=[self.editable_order.pk]),
            data={"name": "New Name", "line1": "New Line 1", "city": "New City", "state": "New State", "pincode": "222222"},
        )
        self.assertRedirects(response, reverse("dashboard:order-detail", args=[self.editable_order.pk]))
        self.editable_order.refresh_from_db()
        self.assertEqual(self.editable_order.delivery_address_snapshot["line1"], "New Line 1")
        self.assertEqual(self.editable_order.delivery_address_snapshot["city"], "New City")

    def test_blocked_status_rejects_update(self) -> None:
        response = self.client.post(
            reverse("dashboard:order-address-update", args=[self.delivered_order.pk]),
            data={"name": "New Name", "line1": "New Line 1", "city": "New City"},
        )
        self.assertRedirects(response, reverse("dashboard:order-detail", args=[self.delivered_order.pk]))
        self.delivered_order.refresh_from_db()
        self.assertEqual(self.delivered_order.delivery_address_snapshot["line1"], "Frozen Line 1")


class ProductVariantHasChangedTests(TestCase):
    """
    A variant row an admin explicitly filled with legitimate-but-default-
    looking values (stock 0, threshold 5) must not be silently dropped as an
    "untouched extra" row.
    """

    def test_explicit_zero_values_count_as_changed(self) -> None:
        data = {
            "variants-0-variant_type": "",
            "variants-0-name": "",
            "variants-0-base_price": "0",
            "variants-0-mrp": "0",
            "variants-0-purchase_price": "0",
            "variants-0-sku_suffix": "",
            "variants-0-stock_quantity": "0",
            "variants-0-low_stock_threshold": "5",
        }
        form = ProductVariantForm(data, prefix="variants-0")
        self.assertTrue(form.has_changed())

    def test_fully_blank_row_is_unchanged(self) -> None:
        data = {
            "variants-0-variant_type": "",
            "variants-0-name": "",
            "variants-0-base_price": "",
            "variants-0-mrp": "",
            "variants-0-purchase_price": "",
            "variants-0-sku_suffix": "",
            "variants-0-stock_quantity": "",
            "variants-0-low_stock_threshold": "",
        }
        form = ProductVariantForm(data, prefix="variants-0")
        self.assertFalse(form.has_changed())


class ProductVariantFormSetValidationTests(TestCase):
    """Cross-row validation added to ProductVariantInlineFormSet."""

    def setUp(self) -> None:
        self.product = Product.objects.create(
            name="Formset Yarn",
            slug="formset-yarn",
            sku="SKU-FORMSET-1",
            base_price="100.00",
            mrp="100.00",
            purchase_price="60.00",
        )

    def _management_form(self, total: int) -> dict:
        return {
            "variants-TOTAL_FORMS": str(total),
            "variants-INITIAL_FORMS": "0",
            "variants-MIN_NUM_FORMS": "0",
            "variants-MAX_NUM_FORMS": "1000",
        }

    def _row(self, index: int, **overrides) -> dict:
        row = {
            f"variants-{index}-variant_type": "Size",
            f"variants-{index}-name": f"Variant {index}",
            f"variants-{index}-base_price": "90.00",
            f"variants-{index}-mrp": "90.00",
            f"variants-{index}-purchase_price": "50.00",
            f"variants-{index}-sku_suffix": f"SKU{index}",
            f"variants-{index}-stock_quantity": "5",
            f"variants-{index}-low_stock_threshold": "5",
        }
        for key, value in overrides.items():
            row[f"variants-{index}-{key}"] = value
        return row

    def test_duplicate_sku_suffix_rejected(self) -> None:
        data = self._management_form(2)
        data.update(self._row(0, sku_suffix="Small"))
        data.update(self._row(1, sku_suffix="small"))  # case-insensitive collision
        formset = ProductVariantFormSet(data, instance=self.product, prefix="variants")
        self.assertFalse(formset.is_valid())

    def test_variant_type_casing_normalized_to_first_seen(self) -> None:
        data = self._management_form(2)
        data.update(self._row(0, variant_type="Size"))
        data.update(self._row(1, variant_type="size", sku_suffix="SKU1"))
        formset = ProductVariantFormSet(data, instance=self.product, prefix="variants")
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.forms[1].cleaned_data["variant_type"], "Size")

    def test_only_one_default_variant_allowed(self) -> None:
        data = self._management_form(2)
        data.update(self._row(0, is_default="on"))
        data.update(self._row(1, is_default="on"))
        formset = ProductVariantFormSet(data, instance=self.product, prefix="variants")
        self.assertFalse(formset.is_valid())


class ProductFormRequiredPriceGateTests(TestCase):
    """
    ProductForm.clean() silently defaults blank base_price/mrp/purchase_price/
    stock_quantity to 0 — fine when a variant will drive those fields, but a
    variant-less product must actually require them, matching the form's own
    (previously dead) error_messages.
    """

    def setUp(self) -> None:
        self.staff_user = User.objects.create_superuser(
            username="dash-admin-price", email="dash-admin-price@example.com", password="testpass12345"
        )
        self.client.force_login(self.staff_user)

    def _base_post(self, **overrides) -> dict:
        data = {
            "name": "Priced Yarn",
            "sku": "SKU-PRICE-1",
            "variants-TOTAL_FORMS": "0",
            "variants-INITIAL_FORMS": "0",
            "variants-MIN_NUM_FORMS": "0",
            "variants-MAX_NUM_FORMS": "1000",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            "specifications-TOTAL_FORMS": "0",
            "specifications-INITIAL_FORMS": "0",
            "specifications-MIN_NUM_FORMS": "0",
            "specifications-MAX_NUM_FORMS": "1000",
        }
        data.update(overrides)
        return data

    def test_no_variants_and_blank_prices_is_rejected(self) -> None:
        response = self.client.post(reverse("dashboard:product-create"), data=self._base_post())
        self.assertEqual(response.status_code, 200)  # re-renders the form with errors
        self.assertFalse(Product.objects.filter(sku="SKU-PRICE-1").exists())

    def test_rejection_explains_which_fields_are_missing(self) -> None:
        response = self.client.post(reverse("dashboard:product-create"), data=self._base_post())
        body = response.content.decode()
        self.assertIn('id="product-form-errors"', body)
        self.assertIn("The product was not saved", body)
        for field_id, message in (
            ("id_base_price", "Base price is required when the product has no variants."),
            ("id_mrp", "MRP is required when the product has no variants."),
            ("id_purchase_price", "Purchase price is required when the product has no variants."),
        ):
            self.assertIn(f'href="#{field_id}"', body)
            self.assertIn(message, body)
        self.assertRegex(body, r'<input[^>]*class="[^"]*is-invalid[^"]*"[^>]*id="id_base_price"')

    def test_invalid_variant_row_shows_errors_under_each_field(self) -> None:
        data = self._base_post(**{
            "variants-TOTAL_FORMS": "1",
            "variants-0-variant_type": "", "variants-0-name": "Small", "variants-0-base_price": "",
            "variants-0-mrp": "", "variants-0-purchase_price": "", "variants-0-sku_suffix": "",
            "variants-0-stock_quantity": "", "variants-0-low_stock_threshold": "",
        })
        response = self.client.post(reverse("dashboard:product-create"), data=data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(sku="SKU-PRICE-1").exists())
        self.assertEqual(dict(response.context["form"].errors), {})
        body = response.content.decode()
        for field, message in (
            ("variant_type", "Variant type is required."),
            ("base_price", "Base price is required."),
            ("mrp", "MRP is required."),
            ("purchase_price", "Purchase price is required."),
            ("stock_quantity", "Stock quantity is required."),
            ("low_stock_threshold", "Low stock threshold is required."),
        ):
            self.assertRegex(body, rf'id="id_variants-0-{field}">\s*<div class="text-danger small mt-1">{message}</div>')
        self.assertNotIn('mt-1">Base price is required when the product has no variants.', body)
        self.assertIn('id="product-form-errors"', body)

    def test_required_markers_on_variant_columns_and_inputs(self) -> None:
        body = self.client.get(reverse("dashboard:product-create")).content.decode()
        for header in ("Type", "Name", "Base Price", "MRP", "Purchase Price", "Stock", "Threshold"):
            self.assertIn(f'<th>{header} <span class="text-danger">*</span></th>', body)
        self.assertIn('[data-formset="variants"] tbody[data-formset-body] tr', body)
        self.assertNotRegex(body, r'<input[^>]*name="variants-__prefix__-base_price"[^>]*value=')
        self.assertIn('name="variants-__prefix__-base_price"', body)
        self.assertRegex(body, r'data-required-msg="Base price is required\."[^>]*name="variants-__prefix__-base_price"'
                               r'|name="variants-__prefix__-base_price"[^>]*data-required-msg="Base price is required\."')

    def test_conditionally_required_fields_show_asterisk(self) -> None:
        body = self.client.get(reverse("dashboard:product-create")).content.decode()
        for field_id in ("id_base_price", "id_mrp", "id_purchase_price", "id_stock_quantity"):
            self.assertRegex(body, rf'for="{field_id}">[^<]*<span class="text-danger">\*</span>')
        self.assertNotIn('id="product-form-errors"', body)

    def test_no_variants_with_prices_is_accepted(self) -> None:
        response = self.client.post(reverse("dashboard:product-create"), data=self._base_post(
            base_price="100.00", mrp="120.00", purchase_price="60.00", stock_quantity="10",
        ))
        self.assertRedirects(response, reverse("dashboard:product-list"))
        self.assertTrue(Product.objects.filter(sku="SKU-PRICE-1").exists())


class OrderInvoiceBillToTests(TestCase):
    """Invoice shows a Bill To block (same as Ship To: checkout has no separate billing address)."""

    def setUp(self) -> None:
        self.staff_user = User.objects.create_superuser(
            username="dash-admin-inv", email="dash-admin-inv@example.com", password="testpass12345"
        )
        self.client.force_login(self.staff_user)
        currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.order = Order.objects.create(
            order_number="#INV-BILLTO",
            idempotency_key="inv-billto",
            order_status=OrderStatus.PLACED_COD,
            total_amount="500.00",
            currency=currency,
            delivery_address_snapshot={
                "name": "Asha Menon", "line1": "12 MG Road", "line2": "Near Park",
                "city": "Kochi", "state": "Kerala", "pincode": "682001", "phone": "9876543210",
            },
        )

    def _assert_bill_and_ship_to(self, body: str) -> None:
        self.assertIn("Bill To", body)
        self.assertIn("Ship To", body)
        bill = body.index("Bill To")
        ship = body.index("Ship To")
        self.assertLess(bill, ship)
        bill_block = body[bill:ship]
        for text in ("Asha Menon", "12 MG Road", "Near Park", "Kochi, Kerala 682001", "9876543210"):
            self.assertIn(text, bill_block)
            self.assertIn(text, body[ship:])

    def test_single_invoice_shows_bill_to(self) -> None:
        response = self.client.get(reverse("dashboard:order-invoice", args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self._assert_bill_and_ship_to(response.content.decode())

    def test_bulk_invoice_shows_bill_to(self) -> None:
        response = self.client.post(reverse("dashboard:order-bulk-invoice"), data={"order_ids": [self.order.pk]})
        self.assertEqual(response.status_code, 200)
        self._assert_bill_and_ship_to(response.content.decode())


class ReturningCustomersTests(TestCase):
    """Customers Overview + Reports: 'returning' follows each customer's actual order history."""

    def setUp(self) -> None:
        from datetime import timedelta

        from django.utils import timezone

        self.today = timezone.localdate()
        self.currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={"symbol": "₹", "exchange_rate_to_base": "1.00000000", "is_default": True},
        )
        self.repeat = register_customer_email(email="repeat@example.com", password="testpass12345", name="Repeat")
        self.once = register_customer_email(email="once@example.com", password="testpass12345", name="Once")
        register_customer_email(email="browser@example.com", password="testpass12345", name="Browser")

        self._order(self.repeat, "#RC-1", days_ago=3)
        self._order(self.once, "#RC-2", days_ago=0)
        self._timedelta = timedelta

    def _order(self, profile, number: str, *, days_ago: int, status=OrderStatus.CONFIRMED) -> Order:
        from datetime import timedelta

        from django.utils import timezone

        order = Order.objects.create(
            customer_profile=profile,
            order_number=number,
            idempotency_key=number,
            order_status=status,
            total_amount="100.00",
            currency=self.currency,
        )
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        return order

    def test_repeat_order_moves_customer_to_returning(self) -> None:
        from dashboard.selectors import get_customer_split

        self.assertEqual(get_customer_split()["series"], [100, 0])
        self._order(self.repeat, "#RC-3", days_ago=0)  # existing customer orders again
        self.assertEqual(get_customer_split()["series"], [50, 50])

    def test_cancelled_orders_do_not_count(self) -> None:
        from dashboard.selectors import get_customer_split

        self._order(self.repeat, "#RC-X", days_ago=0, status=OrderStatus.CANCELLED)
        self.assertEqual(get_customer_split()["series"], [100, 0])

    def test_daily_rows_and_live_today(self) -> None:
        from reports.selectors import get_customer_report_rows, get_live_today_customer_report

        self._order(self.repeat, "#RC-3", days_ago=0)
        rows = {
            r.report_date: r
            for r in get_customer_report_rows(start_date=self.today - self._timedelta(days=5), end_date=self.today)
        }
        first_day = rows[self.today - self._timedelta(days=3)]
        self.assertEqual((first_day.new_customers, first_day.returning_customers), (1, 0))
        today_row = rows[self.today]
        self.assertEqual((today_row.new_customers, today_row.returning_customers), (1, 1))
        live = get_live_today_customer_report()
        self.assertEqual((live.new_customers, live.returning_customers, live.total_active_customers), (1, 1, 3))

    def test_reports_page_shows_live_returning_count(self) -> None:
        staff = User.objects.create_superuser("rc-admin", "rc-admin@example.com", "testpass12345")
        self.client.force_login(staff)
        self._order(self.repeat, "#RC-3", days_ago=0)
        response = self.client.get(reverse("dashboard:reports"))
        self.assertEqual(response.status_code, 200)
        today_row = next(c for c in response.context["customers"] if c.report_date == self.today)
        self.assertEqual(today_row.returning_customers, 1)


class ProductImagesKeptAfterFailedSaveTests(TestCase):
    """Images picked before a failed save are kept and reused, not lost."""

    def setUp(self) -> None:
        import tempfile

        from django.test import override_settings

        self._media = tempfile.TemporaryDirectory()
        self._override = override_settings(MEDIA_ROOT=self._media.name)
        self._override.enable()
        staff = User.objects.create_superuser("img-admin", "img-admin@example.com", "testpass12345")
        self.client.force_login(staff)
        self.url = reverse("dashboard:product-create")

    def tearDown(self) -> None:
        self._override.disable()
        self._media.cleanup()

    @staticmethod
    def _png(name: str):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, "PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def _data(self, **overrides) -> dict:
        data = {"name": "Kept Image Saree", "sku": "SKU-KEEP-1", "stock_quantity": "3", "low_stock_threshold": "1"}
        for prefix, total in (("variants", "0"), ("images", "1"), ("specifications", "0")):
            data.update({
                f"{prefix}-TOTAL_FORMS": total, f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000",
            })
        data.update({"images-0-alt_text": "Front", "images-0-display_order": "0", "images-0-is_primary": "on"})
        data.update(overrides)
        return data

    def test_image_survives_failed_save_and_is_used_on_resubmit(self) -> None:
        import os

        from catalog.models import ProductImage
        from django.core.files.storage import default_storage

        first = self.client.post(self.url, self._data(**{"images-0-image": self._png("front.png")}))
        self.assertEqual(first.status_code, 200)
        self.assertFalse(Product.objects.exists())
        iform = first.context["images"].forms[0]
        token = iform.data.get("images-0-image_pending")
        self.assertTrue(token)
        body = first.content.decode()
        self.assertIn(f'value="{token}"', body)                        # hidden reference rendered
        self.assertIn(iform.pending_urls["image"], body)               # preview shown
        self.assertIn("Kept: front.png", body)
        stashed = iform.pending_paths["image"]
        self.assertTrue(default_storage.exists(stashed))

        second = self.client.post(self.url, self._data(**{
            "base_price": "100", "mrp": "120", "purchase_price": "60", "images-0-image_pending": token,
        }))
        self.assertRedirects(second, reverse("dashboard:product-list"))
        image = ProductImage.objects.get(product__sku="SKU-KEEP-1")
        self.assertTrue(image.image.name.startswith("products/images/"))
        self.assertEqual(os.path.basename(image.image.name).split("_")[0].split(".")[0], "front")
        self.assertTrue(image.is_primary)
        self.assertFalse(default_storage.exists(stashed))              # temp copy cleaned up

    def test_tampered_reference_is_ignored(self) -> None:
        response = self.client.post(self.url, self._data(**{
            "base_price": "100", "mrp": "120", "purchase_price": "60",
            "images-0-image_pending": "products/images/someone-elses.jpg",
        }))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.exists())
        self.assertIn("image", response.context["images"].forms[0].errors)
