"""Set the real SIRI COUTURE logo, WhatsApp number, and store address (idempotent)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.services import get_site_settings

NEW_LOGO = "site/siirlogo.png"
NEW_WHATSAPP_NUMBER = "+917795843399"
NEW_STORE_ADDRESS = "Abhish Mall, 1st Floor\nSiiri, Surathkal\nKarnataka 575014"


class Command(BaseCommand):
    help = "Set the real SIRI COUTURE logo, WhatsApp number, and store address on the SiteSettings singleton."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="Report changes without saving.")

    def handle(self, *args, **options) -> None:
        site = get_site_settings()
        changes: dict[str, str] = {}

        if site.logo.name != NEW_LOGO:
            changes["logo"] = NEW_LOGO
        if (site.whatsapp_number or "").strip() != NEW_WHATSAPP_NUMBER:
            changes["whatsapp_number"] = NEW_WHATSAPP_NUMBER
        if (site.store_address or "").strip() != NEW_STORE_ADDRESS:
            changes["store_address"] = NEW_STORE_ADDRESS

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
