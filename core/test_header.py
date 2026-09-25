"""Storefront header: announcement bar, hanging logo card, icon actions."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.services import get_site_settings


def _set(**fields) -> None:
    site = get_site_settings()
    for key, value in fields.items():
        setattr(site, key, value)
    site.save()


class HeaderTests(TestCase):
    def _home(self) -> str:
        response = self.client.get(reverse("cms:homepage"))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_announcement_bar_hidden_when_blank(self):
        _set(announcement_messages="")
        html = self._home()
        header = html.split("<header", 1)[1].split("</header>", 1)[0]
        self.assertNotIn('class="siri-announce"', header)
        self.assertNotIn("jm-topbar", header)

    def test_announcement_bar_parses_icons(self):
        _set(announcement_messages="truck: Free delivery\nPlain message\nnope: Unknown icon")
        header = self._home().split("<header", 1)[1].split("</header>", 1)[0]
        self.assertIn('class="siri-announce"', header)
        self.assertEqual(header.count('class="siri-announce__item"'), 3)
        self.assertIn("siri-icon--truck", header)
        self.assertNotIn("siri-icon--nope", header)
        self.assertIn("<span>Free delivery</span>", header)
        self.assertIn("<span>nope: Unknown icon</span>", header)

    def test_phone_link_only_with_number(self):
        _set(announcement_messages="Hello", whatsapp_number="")
        self.assertNotIn("siri-announce__phone", self._home())
        _set(whatsapp_number="+15550100")
        self.assertIn('href="tel:+15550100"', self._home())

    def test_tagline_shown_and_hidden(self):
        _set(site_tagline="Tradition meets today")
        self.assertIn("Tradition meets today", self._home())
        _set(site_tagline="")
        self.assertNotIn("siri-logo-card__tagline", self._home())

    def test_actions_and_hooks_present(self):
        html = self._home()
        for needle in (
            'id="jm-header-wishlist"',
            'id="wishlist-count-badge"',
            'id="cart-count-badge"',
            'id="mobile-search-open"',
            'id="mobile-search-overlay"',
            'data-bs-target="#cartOffcanvas"',
            'id="jmMainNav"',
        ):
            self.assertIn(needle, html)
        # inline desktop search form was replaced by the shared search sheet
        self.assertNotIn("site-search-input", html)
        self.assertIn(f'action="{reverse("catalog:plp")}"', html)

    def test_renders_for_logged_in_user(self):
        user = User.objects.create_user("h@example.com", "h@example.com", "pw-12345-pw")
        self.client.force_login(user)
        html = self._home()
        self.assertIn(reverse("accounts:logout"), html)
        self.assertIn('id="jm-header-wishlist"', html)
