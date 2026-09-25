"""Django admin registrations for the core app."""

from __future__ import annotations

from django.contrib import admin

from core.forms import CurrencyAdminForm
from core.models import Currency, SiteSettings, State


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """Admin interface for storefront currencies."""

    form = CurrencyAdminForm
    list_display = ("code", "symbol", "exchange_rate_to_base", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("code", "symbol")
    ordering = ("code",)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Singleton site settings — only one row (pk=1)."""

    fieldsets = (
        (
            "Feature switches",
            {
                "fields": (
                    "delivery_integration_enabled",
                    "brands_enabled",
                    "subscriptions_enabled",
                    "rentals_enabled",
                    "gift_builder_enabled",
                    "newsletter_enabled",
                ),
            },
        ),
        (
            "Branding",
            {
                "fields": (
                    "site_name",
                    "logo",
                    "site_tagline",
                    "announcement_messages",
                    "primary_color",
                    "secondary_color",
                    "font_family",
                ),
            },
        ),
        (
            "Contact & social",
            {
                "fields": (
                    "whatsapp_number",
                    "store_address",
                    "vendor_email",
                    "order_notification_email",
                    "facebook_url",
                    "instagram_url",
                    "twitter_url",
                ),
            },
        ),
        (
            "Commerce",
            {
                "fields": (
                    "default_currency",
                    "default_language",
                    "tax_rate_percent",
                    "cod_delivery_charge",
                    "razorpay_key_id",
                    "razorpay_key_secret",
                    "card_gateway_public_key_env",
                    "qatar_gateway_public_key_env",
                    "order_email_template_slug",
                    "whatsapp_template_slug",
                ),
            },
        ),
    )

    def has_add_permission(self, request) -> bool:
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    """Admin interface for delivery states/provinces."""
    
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)
