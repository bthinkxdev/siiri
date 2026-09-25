"""Drag-and-drop ordering of homepage sections + silent autoplay home video."""

from __future__ import annotations

import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from cms.models import HomeVideo, HomepageSection, HomepageSectionType


def _make_sections() -> list[HomepageSection]:
    kinds = [
        HomepageSectionType.HERO_SLIDER,
        HomepageSectionType.SHOP_BY_CATEGORY,
        HomepageSectionType.PROMO_BANNERS,
        HomepageSectionType.SERVICE_STRIP,
    ]
    return [
        HomepageSection.objects.create(section_type=kind, title=f"S{i}", display_order=i, is_active=True)
        for i, kind in enumerate(kinds)
    ]


class ReorderEndpointTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.sections = _make_sections()
        self.url = reverse("dashboard:homepagesection-reorder")
        self.staff = User.objects.create_superuser("admin", "a@example.com", "pw12345678")
        self.client.force_login(self.staff)

    def _post(self, payload, client=None):
        return (client or self.client).post(self.url, data=json.dumps(payload), content_type="application/json")

    def test_reorders_and_persists(self) -> None:
        ids = [s.pk for s in self.sections]
        new_order = [ids[3], ids[0], ids[2], ids[1]]
        response = self._post({"order": new_order})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(HomepageSection.objects.values_list("pk", flat=True)), new_order)

    def test_storefront_follows_new_order(self) -> None:
        ids = [s.pk for s in self.sections]
        self._post({"order": [ids[2], ids[3], ids[1], ids[0]]})
        from cms.selectors import get_active_homepage_sections

        types = [s["section_type"] for s in get_active_homepage_sections()]
        self.assertEqual(
            types,
            [
                HomepageSectionType.PROMO_BANNERS,
                HomepageSectionType.SERVICE_STRIP,
                HomepageSectionType.SHOP_BY_CATEGORY,
                HomepageSectionType.HERO_SLIDER,
            ],
        )

    def test_rejects_malformed_payloads(self) -> None:
        ids = [s.pk for s in self.sections]
        for payload in ({}, {"order": "x"}, {"order": []}, {"order": [1, "2"]}, {"order": [True, 2]}, {"order": [ids[0], ids[0], ids[1], ids[2]]}):
            self.assertEqual(self._post(payload).status_code, 400, payload)
        bad_json = self.client.post(self.url, data="not json", content_type="application/json")
        self.assertEqual(bad_json.status_code, 400)

    def test_rejects_stale_or_partial_lists_with_409(self) -> None:
        ids = [s.pk for s in self.sections]
        self.assertEqual(self._post({"order": ids[:3]}).status_code, 409)  # missing one
        self.assertEqual(self._post({"order": ids + [99999]}).status_code, 409)  # unknown id
        # nothing changed
        self.assertEqual([s.display_order for s in HomepageSection.objects.all()], [0, 1, 2, 3])

    def test_requires_post_and_dashboard_access(self) -> None:
        self.assertEqual(self.client.get(self.url).status_code, 405)
        anonymous = Client()
        response = self._post({"order": [s.pk for s in self.sections]}, client=anonymous)
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual([s.display_order for s in HomepageSection.objects.all()], [0, 1, 2, 3])
        customer = User.objects.create_user("shopper", "s@example.com", "pw12345678")
        shopper_client = Client()
        shopper_client.force_login(customer)
        self.assertEqual(self._post({"order": [s.pk for s in self.sections]}, client=shopper_client).status_code, 403)

    def test_csrf_is_enforced(self) -> None:
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.staff)
        response = strict.post(self.url, data=json.dumps({"order": [s.pk for s in self.sections]}), content_type="application/json")
        self.assertEqual(response.status_code, 403)


class SectionListAndFormTests(TestCase):
    def setUp(self) -> None:
        self.sections = _make_sections()
        self.client.force_login(User.objects.create_superuser("admin", "a@example.com", "pw12345678"))

    def test_list_page_has_drag_handles_and_no_order_column(self) -> None:
        body = self.client.get(reverse("dashboard:homepagesection-list")).content.decode()
        self.assertEqual(body.count("data-reorder-handle"), 4)
        self.assertIn('data-reorder-url="', body)
        self.assertIn("js/reorder.js", body)
        self.assertNotIn("<th>Order</th>", body)
        self.assertEqual(body.count('data-move="up"'), 4)

    def test_other_lists_are_not_draggable(self) -> None:
        body = self.client.get(reverse("dashboard:promobanner-list")).content.decode()
        self.assertNotIn("data-reorder-handle", body)
        self.assertNotIn("reorder.js", body)

    def test_all_sections_listed_on_one_page(self) -> None:
        for i in range(30):
            HomepageSection.objects.create(section_type=HomepageSectionType.NEWSLETTER, display_order=10 + i)
        body = self.client.get(reverse("dashboard:homepagesection-list")).content.decode()
        self.assertEqual(body.count("data-reorder-id="), 34)

    def test_form_has_no_order_field_and_new_section_goes_last(self) -> None:
        from dashboard.forms import HomepageSectionForm

        self.assertNotIn("display_order", HomepageSectionForm().fields)
        response = self.client.post(
            reverse("dashboard:homepagesection-create"),
            {"section_type": HomepageSectionType.NEWSLETTER, "title": "New", "is_active": "on", "config": "{}"},
        )
        self.assertEqual(response.status_code, 302)
        created = HomepageSection.objects.get(title="New")
        self.assertEqual(created.display_order, 4)  # after 0..3

    def test_editing_a_section_keeps_its_position(self) -> None:
        section = self.sections[1]
        self.client.post(
            reverse("dashboard:homepagesection-update", args=[section.pk]),
            {"section_type": section.section_type, "title": "Renamed", "is_active": "on", "config": "{}"},
        )
        section.refresh_from_db()
        self.assertEqual((section.title, section.display_order), ("Renamed", 1))


class AutoplayVideoTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        HomepageSection.objects.create(section_type=HomepageSectionType.VIDEO_SECTION, display_order=1, is_active=True)
        HomeVideo.objects.create(title="Loom", video="cms/video/a.mp4", poster="cms/video/posters/p.jpg")

    def test_video_autoplays_silently_without_controls(self) -> None:
        body = self.client.get("/").content.decode()
        start = body.index("<video class=\"hm-video__player\"")
        tag = body[start:body.index(">", start)]
        for attr in ("autoplay", "muted", "loop", "playsinline", "data-autoplay-video"):
            self.assertIn(attr, tag)
        self.assertNotIn("controls", tag)
        self.assertIn('poster="/media/cms/video/posters/p.jpg"', tag)
        self.assertIn("js/autoplay-video.js", body)
