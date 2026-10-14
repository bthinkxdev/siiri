"""Tests for the homepage testimonials and video sections."""

from __future__ import annotations

import tempfile

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from cms.models import (
    MAX_HOME_VIDEO_MB,
    HomeVideo,
    HomepageSection,
    HomepageSectionType,
    Testimonial,
    validate_video_size,
)
from cms.selectors import get_home_video, get_home_videos, get_testimonials


def _section(section_type: str, title: str = "", order: int = 1) -> None:
    HomepageSection.objects.create(
        section_type=section_type, title=title, display_order=order, is_active=True
    )


class TestimonialsSectionTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_renders_name_words_rating_and_initial_avatar(self) -> None:
        _section(HomepageSectionType.TESTIMONIALS, title="Loved by brides")
        Testimonial.objects.create(name="Anjali", location="Kochi", quote="The silk is lovely.", rating=4)
        body = self.client.get("/").content.decode()
        self.assertIn("hm-testi", body)
        self.assertIn("Loved by brides", body)
        self.assertIn("Anjali", body)
        self.assertIn("Kochi", body)
        self.assertIn("The silk is lovely.", body)
        self.assertIn("hm-testi__avatar--initial", body)  # no photo -> initial
        self.assertIn("Rated 4 out of 5", body)

    def test_default_title_when_section_title_blank(self) -> None:
        _section(HomepageSectionType.TESTIMONIALS)
        Testimonial.objects.create(name="Meera", quote="Beautiful.")
        self.assertIn("What Our Customers Say", self.client.get("/").content.decode())

    def test_stars_hidden_without_rating_and_inactive_hidden(self) -> None:
        _section(HomepageSectionType.TESTIMONIALS)
        Testimonial.objects.create(name="Visible", quote="Nice.")
        Testimonial.objects.create(name="Hidden", quote="Secret.", is_active=False)
        body = self.client.get("/").content.decode()
        self.assertNotIn("hm-testi__stars", body)
        self.assertIn("Visible", body)
        self.assertNotIn("Hidden", body)

    def test_renders_nothing_without_testimonials(self) -> None:
        _section(HomepageSectionType.TESTIMONIALS)
        self.assertNotIn("hm-testi", self.client.get("/").content.decode())

    def test_selector_orders_and_limits(self) -> None:
        for i in range(8):
            Testimonial.objects.create(name=f"N{i}", quote="q", display_order=8 - i)
        names = [t["name"] for t in get_testimonials(limit=6)]
        self.assertEqual(names, ["N7", "N6", "N5", "N4", "N3", "N2"])

    def test_rating_range_validated(self) -> None:
        item = Testimonial(name="X", quote="q", rating=9)
        with self.assertRaises(ValidationError):
            item.full_clean()


class HomeVideoSectionTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_video_renders_with_dynamic_title_and_source(self) -> None:
        _section(HomepageSectionType.VIDEO_SECTION, title="Fallback title")
        HomeVideo.objects.create(title="Weaving a saree", subtitle="Behind the loom", video="cms/video/loom.mp4")
        body = self.client.get("/").content.decode()
        self.assertIn("hm-video__player", body)
        self.assertIn("Weaving a saree", body)
        self.assertIn("Behind the loom", body)
        self.assertIn('type="video/mp4"', body)
        self.assertIn("/media/cms/video/loom.mp4", body)

    def test_section_title_used_when_video_title_blank(self) -> None:
        _section(HomepageSectionType.VIDEO_SECTION, title="From the section")
        HomeVideo.objects.create(video="cms/video/x.webm")
        body = self.client.get("/").content.decode()
        self.assertIn("From the section", body)
        self.assertIn('type="video/webm"', body)

    def test_renders_nothing_without_active_video(self) -> None:
        _section(HomepageSectionType.VIDEO_SECTION)
        HomeVideo.objects.create(title="Off", video="cms/video/x.mp4", is_active=False)
        self.assertNotIn("hm-video", self.client.get("/").content.decode())
        self.assertIsNone(get_home_video())

    def test_all_active_videos_render_in_display_order(self) -> None:
        _section(HomepageSectionType.VIDEO_SECTION)
        HomeVideo.objects.create(title="Old", video="cms/video/old.mp4")
        HomeVideo.objects.create(title="New", video="cms/video/new.mp4")
        HomeVideo.objects.create(title="Hidden", video="cms/video/off.mp4", is_active=False)
        self.assertEqual([v["title"] for v in get_home_videos()], ["Old", "New"])
        body = self.client.get("/").content.decode()
        self.assertEqual(body.count('class="hm-video__player"'), 2)
        self.assertLess(body.index("/media/cms/video/old.mp4"), body.index("/media/cms/video/new.mp4"))
        self.assertNotIn("/media/cms/video/off.mp4", body)
        self.assertEqual(body.count("js/autoplay-video.js"), 1)

    def test_display_order_controls_sequence(self) -> None:
        HomeVideo.objects.create(title="Second", video="cms/video/a.mp4", display_order=2)
        HomeVideo.objects.create(title="First", video="cms/video/b.mp4", display_order=1)
        self.assertEqual([v["title"] for v in get_home_videos()], ["First", "Second"])
        self.assertEqual(get_home_video()["title"], "First")

    def test_size_validator(self) -> None:
        class Big:
            size = (MAX_HOME_VIDEO_MB + 1) * 1024 * 1024

        class Small:
            size = 1024

        validate_video_size(Small())
        with self.assertRaises(ValidationError):
            validate_video_size(Big())


class DashboardTestimonialVideoTests(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_superuser("admin", "a@example.com", "pw12345678")
        self.client.force_login(self.staff)

    def test_list_and_create_pages_load(self) -> None:
        for name in ("testimonial-list", "testimonial-create", "homevideo-list", "homevideo-create"):
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 200, name)

    def test_create_testimonial(self) -> None:
        response = self.client.post(
            reverse("dashboard:testimonial-create"),
            {"name": "Riya", "quote": "Gorgeous saree.", "rating": 5, "display_order": 0, "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Testimonial.objects.get().name, "Riya")

    def test_upload_video_and_reject_wrong_extension(self) -> None:
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            url = reverse("dashboard:homevideo-create")
            bad = self.client.post(url, {"title": "T", "video": SimpleUploadedFile("x.exe", b"MZ"), "is_active": "on"})
            self.assertEqual(bad.status_code, 200)
            self.assertEqual(HomeVideo.objects.count(), 0)
            ok = self.client.post(
                url, {"title": "Loom", "video": SimpleUploadedFile("loom.mp4", b"\x00\x00\x00\x18ftypmp42"), "is_active": "on"}
            )
            self.assertEqual(ok.status_code, 302)
            self.assertEqual(HomeVideo.objects.get().title, "Loom")


class CategoryCardsRemovedTests(TestCase):
    def test_category_cards_is_no_longer_a_section_type(self) -> None:
        self.assertNotIn("category_cards", HomepageSectionType.values)
