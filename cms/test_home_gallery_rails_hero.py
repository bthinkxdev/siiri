"""Tests for the memories gallery, homepage product rails, hero video and full-bleed video."""

from __future__ import annotations

import io
import tempfile

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Product
from cms.models import (
    HeroSlide,
    HomeVideo,
    HomepageSection,
    HomepageSectionType,
    MemoryPhoto,
    validate_video_size,
)
from cms.selectors import get_memory_photos


def _section(section_type: str, title: str = "", order: int = 1, config: dict | None = None) -> None:
    HomepageSection.objects.create(
        section_type=section_type, title=title, display_order=order, is_active=True, config=config or {}
    )


def _make_product(slug: str, **flags) -> Product:
    return Product.objects.create(
        name=f"Saree {slug}",
        slug=slug,
        sku=f"SKU-{slug}",
        base_price="900.00",
        mrp="900.00",
        purchase_price="500.00",
        stock_quantity=5,
        **flags,
    )


def _png(width: int, height: int, name: str = "x.png") -> SimpleUploadedFile:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (90, 20, 20)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class MemoriesSectionTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_renders_photos_in_order_with_captions_and_controls(self) -> None:
        _section(HomepageSectionType.MEMORIES, title="Good Times")
        MemoryPhoto.objects.create(image="cms/memories/b.jpg", caption="Second", display_order=2)
        MemoryPhoto.objects.create(image="cms/memories/a.jpg", caption="First", display_order=1)
        MemoryPhoto.objects.create(image="cms/memories/x.jpg", caption="Hidden", display_order=3, is_active=False)
        body = self.client.get("/").content.decode()
        self.assertIn("data-memories", body)
        self.assertIn("Good Times", body)
        self.assertLess(body.index("First"), body.index("Second"))
        self.assertNotIn("Hidden", body)
        self.assertEqual(body.count("data-memories-dash"), 2)
        self.assertIn("js/memories.js", body)
        self.assertIn("data-memories-prev", body)

    def test_default_title_and_subtitle_from_config(self) -> None:
        _section(HomepageSectionType.MEMORIES, config={"subtitle": "With our family"})
        MemoryPhoto.objects.create(image="cms/memories/a.jpg")
        body = self.client.get("/").content.decode()
        self.assertIn("Our Memories", body)
        self.assertIn("With our family", body)

    def test_single_photo_has_no_dashes_and_empty_renders_nothing(self) -> None:
        _section(HomepageSectionType.MEMORIES)
        self.assertNotIn("hm-mem", self.client.get("/").content.decode())
        MemoryPhoto.objects.create(image="cms/memories/a.jpg")
        body = self.client.get("/").content.decode()
        self.assertIn("hm-mem", body)
        self.assertNotIn("data-memories-dash", body)

    def test_selector_limit(self) -> None:
        for i in range(15):
            MemoryPhoto.objects.create(image=f"cms/memories/{i}.jpg", display_order=i)
        self.assertEqual(len(get_memory_photos()), 12)


class MemoryPhotoDashboardTests(TestCase):
    def setUp(self) -> None:
        self.client.force_login(User.objects.create_superuser("admin", "a@example.com", "pw12345678"))

    def test_pages_load(self) -> None:
        for name in ("memoryphoto-list", "memoryphoto-create"):
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 200, name)

    def test_upload_min_width(self) -> None:
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            url = reverse("dashboard:memoryphoto-create")
            small = self.client.post(url, {"image": _png(300, 375), "display_order": 0, "is_active": "on"})
            self.assertEqual(small.status_code, 200)
            ok = self.client.post(
                url, {"image": _png(800, 1000), "caption": "Riya", "display_order": 0, "is_active": "on"}
            )
            self.assertEqual(ok.status_code, 302)
        self.assertEqual(MemoryPhoto.objects.get().caption, "Riya")


class ProductRailSectionTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_new_arrivals_falls_back_to_newest_when_none_flagged(self) -> None:
        _section(HomepageSectionType.NEW_ARRIVALS, title="Recently Added")
        _make_product("one")
        body = self.client.get("/").content.decode()
        self.assertIn("Recently Added", body)
        self.assertIn("Saree one", body)
        self.assertIn("?new_arrival=1", body)

    def test_new_arrivals_prefers_flagged_products(self) -> None:
        _section(HomepageSectionType.NEW_ARRIVALS)
        _make_product("plain")
        _make_product("flagged", is_new_arrival=True)
        body = self.client.get("/").content.decode()
        self.assertIn("Saree flagged", body)
        self.assertNotIn("Saree plain", body)

    def test_best_sellers_hidden_until_flagged(self) -> None:
        _section(HomepageSectionType.BEST_SELLERS)
        _make_product("one")
        self.assertNotIn("hm-rail", self.client.get("/").content.decode())
        _make_product("top", is_bestseller=True)
        body = self.client.get("/").content.decode()
        self.assertIn("hm-rail", body)
        self.assertIn("Saree top", body)
        self.assertIn("?bestseller=1", body)

    def test_featured_uses_default_title_and_rail_contract(self) -> None:
        _section(HomepageSectionType.FEATURED_PRODUCTS)
        _make_product("one")
        body = self.client.get("/").content.decode()
        self.assertIn("Featured", body)
        # markup the rail JS depends on
        for hook in ("data-rail-track", 'data-rail-scroll="prev"', 'data-rail-scroll="next"', "jm-featured__rail"):
            self.assertIn(hook, body)

    def test_view_all_plp_falls_back_when_none_flagged(self) -> None:
        _make_product("one")
        plp = reverse("catalog:plp")
        for param in ("new_arrival", "featured"):
            body = self.client.get(f"{plp}?{param}=1").content.decode()
            self.assertIn("Saree one", body, param)

    def test_view_all_plp_prefers_flagged_products(self) -> None:
        _make_product("plain")
        _make_product("new", is_new_arrival=True)
        _make_product("feat", is_featured=True)
        plp = reverse("catalog:plp")
        new_body = self.client.get(f"{plp}?new_arrival=1").content.decode()
        self.assertIn("Saree new", new_body)
        self.assertNotIn("Saree plain", new_body)
        feat_body = self.client.get(f"{plp}?featured=1").content.decode()
        self.assertIn("Saree feat", feat_body)
        self.assertNotIn("Saree plain", feat_body)

    def test_featured_rail_prefers_flagged_products(self) -> None:
        _section(HomepageSectionType.FEATURED_PRODUCTS)
        _make_product("plain")
        _make_product("feat", is_featured=True)
        body = self.client.get("/").content.decode()
        self.assertIn("Saree feat", body)
        self.assertNotIn("Saree plain", body)

    def test_empty_sections_render_nothing(self) -> None:
        for kind in (
            HomepageSectionType.NEW_ARRIVALS,
            HomepageSectionType.FEATURED_PRODUCTS,
            HomepageSectionType.BEST_SELLERS,
        ):
            _section(kind)
        self.assertNotIn("hm-rail", self.client.get("/").content.decode())


class HeroVideoTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        _section(HomepageSectionType.HERO_SLIDER)

    def test_video_slide_markup_and_script(self) -> None:
        HeroSlide.objects.create(
            title="Vid", video="cms/hero/videos/a.webm", poster="cms/hero/posters/p.jpg", display_order=1
        )
        body = self.client.get("/").content.decode()
        self.assertIn("data-hero-video", body)
        self.assertIn("muted", body)
        self.assertIn("playsinline", body)
        self.assertIn('type="video/webm"', body)
        self.assertIn('poster="/media/cms/hero/posters/p.jpg"', body)
        self.assertIn("js/hero-video.js", body)

    def test_image_only_hero_does_not_load_video_script(self) -> None:
        HeroSlide.objects.create(title="Img", image="cms/hero/images/a.jpg", display_order=1)
        body = self.client.get("/").content.decode()
        self.assertNotIn("hero-video.js", body)
        self.assertNotIn("data-hero-video", body)

    def test_only_first_video_autoplays(self) -> None:
        HeroSlide.objects.create(title="A", video="cms/hero/videos/a.mp4", display_order=1)
        HeroSlide.objects.create(title="B", video="cms/hero/videos/b.mp4", display_order=2)
        body = self.client.get("/").content.decode()
        self.assertEqual(body.count("autoplay"), 1)

    def test_video_size_limit_applies_to_hero(self) -> None:
        self.assertIn(validate_video_size, HeroSlide._meta.get_field("video").validators)

    def test_poster_accepts_banner_ratio_and_rejects_square(self) -> None:
        self.client.force_login(User.objects.create_superuser("admin", "a@example.com", "pw12345678"))
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):

            def post(width: int, height: int):
                return self.client.post(
                    reverse("dashboard:heroslide-create"),
                    {
                        "title": "V",
                        "display_order": 0,
                        "is_active": "on",
                        "video": SimpleUploadedFile("v.mp4", b"\x00\x00\x00\x18ftypmp42"),
                        "poster": _png(width, height, "p.png"),
                    },
                )

            self.assertEqual(post(2400, 940).status_code, 302)  # the 2.5:1 banner ratio
            self.assertEqual(post(1200, 1200).status_code, 200)  # square poster rejected


class FullBleedVideoTests(TestCase):
    def test_frame_is_a_direct_child_of_the_section(self) -> None:
        cache.clear()
        _section(HomepageSectionType.VIDEO_SECTION)
        HomeVideo.objects.create(title="T", video="cms/video/a.mp4")
        body = self.client.get("/").content.decode()
        start = body.index('<section class="hm-video"')
        frame = body.index('class="hm-video__frame"')
        wrapper_close = body.index("</div>", body.index('class="hm-wrap"', start))
        # the heading wrapper closes before the frame opens, so the frame is not inside the padded wrapper
        self.assertLess(wrapper_close, frame)
