"""Tests for core management commands."""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.services import get_site_settings


class ResetBrandContactTests(TestCase):
    def _run(self, *args: str) -> None:
        call_command("reset_brand_contact", *args, stdout=StringIO())

    def test_resets_legacy_values_only(self) -> None:
        site = get_site_settings()
        site.site_name = "YARN GUY"
        site.whatsapp_number = "+919961170396"
        site.vendor_email = "YarnGuyOnline@gmail.com"
        site.order_notification_email = "owner@example.com"
        site.save()

        self._run()
        site.refresh_from_db()
        self.assertEqual(site.site_name, "SIRI COUTURE")
        self.assertEqual(site.whatsapp_number, "")
        self.assertEqual(site.vendor_email, "")
        self.assertEqual(site.order_notification_email, "owner@example.com")

        self._run()  # idempotent
        site.refresh_from_db()
        self.assertEqual(site.order_notification_email, "owner@example.com")

    def test_dry_run_saves_nothing(self) -> None:
        site = get_site_settings()
        site.site_name = "YARN GUY"
        site.save()
        self._run("--dry-run")
        site.refresh_from_db()
        self.assertEqual(site.site_name, "YARN GUY")
