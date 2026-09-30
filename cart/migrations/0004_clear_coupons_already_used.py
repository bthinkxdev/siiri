"""
Clear coupons left on carts after a purchase.

Carts are reused across orders. Before the fix in payments.services.confirm_payment_success,
a completed purchase emptied the cart's items but kept its coupon, so the coupon showed up
(and could silently re-apply) on the customer's next checkout. This removes any coupon that
was already redeemed on an order placed from that same cart. Coupons a customer applied but
has not used yet are left untouched.
"""

from decimal import Decimal

from django.db import migrations


def clear_used_coupons(apps, schema_editor):
    Cart = apps.get_model("cart", "Cart")
    CouponRedemption = apps.get_model("marketing", "CouponRedemption")

    for cart in Cart.objects.exclude(coupon_code="").only("pk", "coupon_code"):
        already_used = CouponRedemption.objects.filter(
            order__cart_id=cart.pk,
            coupon__code__iexact=cart.coupon_code.strip(),
        ).exists()
        if already_used:
            Cart.objects.filter(pk=cart.pk).update(coupon_code="", coupon_discount=Decimal("0.00"))


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0003_remove_cart_destination_city"),
        ("marketing", "0007_drop_category"),
        ("orders", "0010_orderitem_variant_name_orderitem_variant_sku_and_more"),
    ]

    operations = [
        migrations.RunPython(clear_used_coupons, migrations.RunPython.noop),
    ]
