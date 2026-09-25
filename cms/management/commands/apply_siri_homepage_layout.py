"""Adapt the homepage section layout to SIRI COUTURE's real content (idempotent)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from cms.models import HomepageSection, ServiceHighlight

DEACTIVATE_SECTION_TYPES = ["featured_products", "best_sellers", "video_section"]

MEMORIES_TITLE = "Moments With SIRI"

SERVICE_HIGHLIGHTS = [
    {"icon": "truck", "label": "Pan-India Delivery", "display_order": 0},
    {"icon": "card", "label": "Cash on Delivery Available", "display_order": 1},
    {"icon": "shield", "label": "Secure Payments", "display_order": 2},
    {"icon": "return", "label": "Easy Returns", "display_order": 3},
]


class Command(BaseCommand):
    help = "Deactivate redundant/leftover homepage sections, retitle Memories, and seed the service strip."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="Report changes without saving.")

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]
        changed = 0

        for section in HomepageSection.objects.filter(section_type__in=DEACTIVATE_SECTION_TYPES, is_active=True):
            self.stdout.write(f"[{section.section_type}] is_active: True -> False")
            changed += 1
            if not dry_run:
                section.is_active = False
                section.save(update_fields=["is_active"])

        hero = HomepageSection.objects.filter(section_type="hero_slider").first()
        if hero and hero.config:
            self.stdout.write(f"[hero_slider] config: {hero.config!r} -> {{}}")
            changed += 1
            if not dry_run:
                hero.config = {}
                hero.save(update_fields=["config"])

        memories = HomepageSection.objects.filter(section_type="memories").first()
        if memories and memories.title != MEMORIES_TITLE:
            self.stdout.write(f"[memories] title: {memories.title!r} -> {MEMORIES_TITLE!r}")
            changed += 1
            if not dry_run:
                memories.title = MEMORIES_TITLE
                memories.save(update_fields=["title"])

        if not ServiceHighlight.objects.exists():
            self.stdout.write(f"[service_highlight] creating {len(SERVICE_HIGHLIGHTS)} rows")
            changed += 1
            if not dry_run:
                ServiceHighlight.objects.bulk_create(ServiceHighlight(**row) for row in SERVICE_HIGHLIGHTS)

        if not changed:
            self.stdout.write("No changes needed.")
        elif dry_run:
            self.stdout.write(f"Dry run: {changed} change(s) would be applied.")
        else:
            self.stdout.write(self.style.SUCCESS(f"{changed} change(s) applied."))
