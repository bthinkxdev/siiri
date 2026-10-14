"""Delete files kept from failed product saves that were never used (older than a day)."""

from __future__ import annotations

from datetime import timedelta

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.pending_uploads import PENDING_UPLOAD_DIR, PENDING_UPLOAD_MAX_AGE


class Command(BaseCommand):
    help = "Remove stale files kept from failed dashboard form saves (run daily, e.g. via cron/Celery beat)."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(seconds=PENDING_UPLOAD_MAX_AGE)
        removed = 0
        try:
            folders, _ = default_storage.listdir(PENDING_UPLOAD_DIR)
        except (FileNotFoundError, OSError):
            folders = []
        for folder in folders:
            base = f"{PENDING_UPLOAD_DIR}{folder}/"
            _, files = default_storage.listdir(base)
            for name in files:
                path = base + name
                if default_storage.get_modified_time(path) < cutoff:
                    default_storage.delete(path)
                    removed += 1
        self.stdout.write(self.style.SUCCESS(f"Removed {removed} stale pending upload(s)."))
