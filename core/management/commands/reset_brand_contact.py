"""Reset legacy YARN GUY brand/contact values on the SiteSettings singleton."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.services import get_site_settings

NEW_SITE_NAME = "SIRI COUTURE"
OLD_WHATSAPP_NUMBER = "+919961170396"
OLD_EMAILS = {"yarnguyonline@gmail.com", "yarnguy.in@gmail.com"}


class Command(BaseCommand):
    help = "Set site_name to SIRI COUTURE and blank legacy YARN GUY contact details (idempotent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="Report changes without saving.")

    def handle(self, *args, **options) -> None:
        site = get_site_settings()
        changes: dict[str, str] = {}

        if site.site_name != NEW_SITE_NAME:
            changes["site_name"] = NEW_SITE_NAME
        if (site.whatsapp_number or "").strip() == OLD_WHATSAPP_NUMBER:
            changes["whatsapp_number"] = ""
        for field in ("vendor_email", "order_notification_email"):
            if (getattr(site, field) or "").strip().lower() in OLD_EMAILS:
                changes[field] = ""

        if not changes:
            self.stdout.write("No changes needed.")
            return

        for field, value in changes.items():
            self.stdout.write(f"{field}: {getattr(site, field)!r} -> {value!r}")
            setattr(site, field, value)

        if options["dry_run"]:
            self.stdout.write("Dry run: nothing saved.")
            return

        site.save(update_fields=list(changes))
        self.stdout.write(self.style.SUCCESS("SiteSettings updated."))
