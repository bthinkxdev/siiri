"""Tests for homepage promo banners and the shared link validator."""

from __future__ import annotations

import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Category
from cms.models import (
    HomepageSection,
    HomepageSectionType,
    PromoBanner,
    PromoBannerStyle,
    ServiceHighlight,
    validate_link_target,
)


class LinkValidatorTests(TestCase):
    def test_accepts_paths_and_http_urls(self) -> None:
        for value in ("/shop/", "/shop/category/sarees/", "http://example.com", "https://example.com/x"):
            validate_link_target(value)

    def test_rejects_script_and_protocol_relative(self) -> None:
        for value in ("javascript:alert(1)", "JAVASCRIPT:alert(1)", "data:text/html,x", "//evil.com", "shop/"):
            with self.assertRaises(ValidationError, msg=value):
                validate_link_target(value)


class HomepageBannerTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def _section(self, section_type: str, order: int, **extra) -> None:
        HomepageSection.objects.create(
            section_type=section_type, title="t", display_order=order, is_active=True, **extra
        )

    def test_banners_render_in_order_and_inactive_hidden(self) -> None:
        self._section(HomepageSectionType.PROMO_BANNERS, 1)
        PromoBanner.objects.create(title="Second", display_order=2, cta_label="Go", cta_url="/shop/")
        PromoBanner.objects.create(title="First", eyebrow="Pure", subtitle="Sub", display_order=1)
        PromoBanner.objects.create(title="Hidden", display_order=3, is_active=False)
        body = self.client.get("/").content.decode()
        self.assertIn("hm-tiles__grid", body)
        self.assertLess(body.index("First"), body.index("Second"))
        self.assertNotIn("Hidden", body)
        self.assertIn('href="/shop/"', body)
        self.assertEqual(body.count("hm-btn--outline"), 1)  # button only when label and link are set

    def test_section_renders_nothing_without_banners(self) -> None:
        self._section(HomepageSectionType.PROMO_BANNERS, 1)
        body = self.client.get("/").content.decode()
        self.assertNotIn("hm-tiles__grid", body)

    def test_banner_without_title_or_image_is_skipped(self) -> None:
        self._section(HomepageSectionType.PROMO_BANNERS, 1)
        PromoBanner.objects.create(eyebrow="only eyebrow")
        self.assertNotIn("hm-tiles__grid", self.client.get("/").content.decode())

    def test_category_circles_render_when_section_active(self) -> None:
        Category.objects.create(name="Sarees", slug="sarees")
        self._section(HomepageSectionType.SHOP_BY_CATEGORY, 1)
        body = self.client.get("/").content.decode()
        self.assertIn("hm-circle", body)
        self.assertIn("Sarees", body)


class PromoBannerDashboardTests(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_superuser("admin", "a@example.com", "pw12345678")
        self.client.force_login(self.staff)

    def test_list_and_create_pages_load(self) -> None:
        self.assertEqual(self.client.get(reverse("dashboard:promobanner-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:promobanner-create")).status_code, 200)

    def test_create_rejects_script_link_and_accepts_path(self) -> None:
        url = reverse("dashboard:promobanner-create")
        bad = self.client.post(url, {"title": "X", "cta_label": "Go", "cta_url": "javascript:alert(1)", "display_order": 0, "is_active": "on"})
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(PromoBanner.objects.count(), 0)
        ok = self.client.post(url, {"title": "X", "cta_label": "Go", "cta_url": "/shop/", "style": "tile", "display_order": 0, "is_active": "on"})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(PromoBanner.objects.get().cta_url, "/shop/")


class HomeSectionsTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def _section(self, section_type: str, order: int = 1, title: str = "", config: dict | None = None) -> None:
        HomepageSection.objects.create(
            section_type=section_type, title=title, display_order=order, config=config or {}
        )

    def _home(self) -> str:
        return self.client.get("/").content.decode()

    def test_promo_section_shows_only_tile_style(self) -> None:
        self._section(HomepageSectionType.PROMO_BANNERS)
        PromoBanner.objects.create(title="TileOne")
        PromoBanner.objects.create(title="WideOne", style=PromoBannerStyle.WIDE)
        body = self._home()
        self.assertIn("TileOne", body)
        self.assertNotIn("WideOne", body)

    def test_wide_banner_shows_first_active_wide_only(self) -> None:
        self._section(HomepageSectionType.WIDE_BANNER)
        PromoBanner.objects.create(title="TileX", style=PromoBannerStyle.TILE)
        PromoBanner.objects.create(title="OffX", style=PromoBannerStyle.WIDE, display_order=0, is_active=False)
        PromoBanner.objects.create(title="WideA", style=PromoBannerStyle.WIDE, display_order=1, cta_label="Go", cta_url="/shop/")
        PromoBanner.objects.create(title="WideB", style=PromoBannerStyle.WIDE, display_order=2)
        body = self._home()
        self.assertIn("hm-wide", body)
        self.assertIn("WideA", body)
        self.assertNotIn("WideB", body)
        self.assertNotIn("TileX", body)
        self.assertNotIn("OffX", body)

    def test_wide_banner_renders_nothing_without_data(self) -> None:
        self._section(HomepageSectionType.WIDE_BANNER)
        PromoBanner.objects.create(title="Tile")
        self.assertNotIn("hm-wide", self._home())

    def test_service_strip_order_inactive_and_empty(self) -> None:
        self._section(HomepageSectionType.SERVICE_STRIP)
        self.assertNotIn("hm-service", self._home())
        ServiceHighlight.objects.create(icon="truck", label="SecondItem", display_order=2)
        ServiceHighlight.objects.create(icon="shield", label="FirstItem", display_order=1)
        ServiceHighlight.objects.create(icon="star", label="HiddenItem", display_order=3, is_active=False)
        body = self._home()
        self.assertLess(body.index("FirstItem"), body.index("SecondItem"))
        self.assertNotIn("HiddenItem", body)
        self.assertIn("siri-icon--shield", body)

    def test_service_selector_single_query(self) -> None:
        from cms.selectors import get_service_highlights

        ServiceHighlight.objects.create(icon="truck", label="A")
        with self.assertNumQueries(1):
            get_service_highlights()

    def test_category_circles_ignore_trust_items(self) -> None:
        Category.objects.create(name="Sarees", slug="sarees")
        self._section(HomepageSectionType.SHOP_BY_CATEGORY, config={"trust_items": [{"title": "NopeItem"}]})
        body = self._home()
        self.assertNotIn("jm-trust", body)
        self.assertNotIn("NopeItem", body)

    def test_hero_has_no_side_arrows_and_renders_copy(self) -> None:
        from cms.models import HeroSlide

        self._section(HomepageSectionType.HERO_SLIDER)
        HeroSlide.objects.create(title="Hero T", image="cms/hero/images/banner1.jpg", cta_label="Go", cta_url="/shop/")
        HeroSlide.objects.create(title="Hero U", image="cms/hero/images/banner2.jpg")
        body = self._home()
        self.assertIn("hm-hero__title", body)
        self.assertIn('id="heroCarousel"', body)
        self.assertNotIn("data-bs-slide=", body)


class DashboardHomeCrudTests(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_superuser("admin2", "b@example.com", "pw12345678")
        self.client.force_login(self.staff)

    def test_service_highlight_crud(self) -> None:
        self.assertEqual(self.client.get(reverse("dashboard:servicehighlight-list")).status_code, 200)
        create = reverse("dashboard:servicehighlight-create")
        self.assertEqual(self.client.get(create).status_code, 200)
        bad = self.client.post(create, {"icon": "nope", "label": "X", "display_order": 0, "is_active": "on"})
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(ServiceHighlight.objects.count(), 0)
        ok = self.client.post(create, {"icon": "truck", "label": "Free shipping", "display_order": 1, "is_active": "on"})
        self.assertEqual(ok.status_code, 302)
        item = ServiceHighlight.objects.get()
        self.assertEqual(self.client.get(reverse("dashboard:servicehighlight-update", args=[item.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("dashboard:servicehighlight-delete", args=[item.pk])).status_code, 302)
        self.assertEqual(ServiceHighlight.objects.count(), 0)

    def test_promo_banner_style_default_and_form(self) -> None:
        url = reverse("dashboard:promobanner-create")
        self.client.post(url, {"title": "W", "style": "wide", "display_order": 0, "is_active": "on"})
        self.client.post(url, {"title": "T", "style": "tile", "display_order": 0, "is_active": "on"})
        self.assertEqual(PromoBanner.objects.get(title="W").style, "wide")
        self.assertEqual(PromoBanner.objects.get(title="T").style, "tile")
        self.assertEqual(PromoBanner.objects.create(title="D").style, "tile")

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class HeroSlideValidationTests(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_superuser("admin3", "c@example.com", "pw12345678")
        self.client.force_login(self.staff)

    def _post(self, width: int, height: int):
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (width, height), (120, 30, 30)).save(buf, "PNG")
        upload = SimpleUploadedFile("h.png", buf.getvalue(), content_type="image/png")
        return self.client.post(
            reverse("dashboard:heroslide-create"),
            {"title": "H", "display_order": 0, "is_active": "on", "image": upload},
        )

    def test_accepted_ratios(self) -> None:
        from cms.models import HeroSlide

        for size in ((2400, 940), (2000, 1000), (2240, 800)):
            self.assertEqual(self._post(*size).status_code, 302, size)
        self.assertEqual(HeroSlide.objects.count(), 3)

    def test_rejected_ratios_and_small_width(self) -> None:
        from cms.models import HeroSlide

        for size in ((1600, 1000), (3200, 900), (800, 300)):
            self.assertEqual(self._post(*size).status_code, 200, size)
        self.assertEqual(HeroSlide.objects.count(), 0)
