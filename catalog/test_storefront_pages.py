"""Smoke tests for the SIRI COUTURE storefront page templates."""

from django.test import TestCase, override_settings
from django.urls import reverse


class StorefrontPagesTests(TestCase):
    def test_public_pages_render(self):
        for name in (
            "catalog:plp",
            "cart:page",
            "core:about-us",
            "core:faq",
            "core:contact-us",
            "core:privacy-policy",
            "accounts:login-email-otp",
            "accounts:register",
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "css/main.css")

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["*"])
    def test_custom_404_template(self):
        response = self.client.get("/definitely-not-a-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "jm-eyebrow", status_code=404)

    def test_footer_contact_block_hidden_without_contact_details(self):
        from core.models import SiteSettings

        settings_obj = SiteSettings.objects.first() or SiteSettings.objects.create()
        settings_obj.whatsapp_number = ""
        settings_obj.vendor_email = ""
        settings_obj.save()
        response = self.client.get(reverse("core:faq"))
        self.assertNotContains(response, "jm-footer__contact")
