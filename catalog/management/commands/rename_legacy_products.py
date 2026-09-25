"""Rename legacy streetwear product names to SIRI COUTURE ethnic-wear names."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from catalog.models import Product

NEW_NAMES: dict[int, str] = {
    # CHURIDHAR SETS
    47: "Piped Churidhar Pants – Camel Beige",
    53: "Piped Churidhar Pants – Light Grey",
    55: "Fleece-Lined Churidhar Pants – Black",
    57: "Classic Churidhar Pants – Dark Grey",
    58: "Piped Churidhar Pants – Mouse Grey",
    59: "Piped Churidhar Pants – Black",
    60: "Piped Churidhar Pants – Jet Black",
    62: "Piped Churidhar Pants – Caramel Brown",
    70: "Piped Churidhar Pants – Smoke Grey",
    # CORDSETS
    56: "Relaxed Co-ord Set – Light Grey",
    # KURTAS
    48: "Cotton Kurta – Lapis Blue",
    49: "Cotton Kurta – White/Red",
    50: "Short Kurti – Red",
    51: "Short Kurti – Black",
    52: "Short Kurti – White",
    54: "Cotton Kurta – White/Brown",
    61: "Cotton Kurta – Black",
    71: "Half-Sleeve Kurta – Dusty Black",
    72: "Half-Sleeve Kurta – Grey",
    73: "Half-Sleeve Kurta – Black",
    74: "Half-Sleeve Kurta – White",
    75: "Half-Sleeve Kurta – Light Grey",
    76: "Half-Sleeve Kurta – Dusty Blue",
}


class Command(BaseCommand):
    help = "Rename legacy streetwear product names to SIRI COUTURE ethnic-wear names (idempotent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="Report changes without saving.")

    def handle(self, *args, **options) -> None:
        products = Product.objects.filter(id__in=NEW_NAMES.keys())
        found_ids = set(products.values_list("id", flat=True))
        missing_ids = set(NEW_NAMES.keys()) - found_ids
        for missing_id in sorted(missing_ids):
            self.stdout.write(self.style.WARNING(f"Product id {missing_id} not found, skipping."))

        changed = 0
        for product in products:
            new_name = NEW_NAMES[product.id]
            if product.name == new_name:
                continue
            self.stdout.write(f"[{product.id}] {product.name!r} -> {new_name!r}")
            changed += 1
            if not options["dry_run"]:
                product.name = new_name
                product.save(update_fields=["name"])

        if not changed:
            self.stdout.write("No changes needed.")
        elif options["dry_run"]:
            self.stdout.write(f"Dry run: {changed} product(s) would be renamed.")
        else:
            self.stdout.write(self.style.SUCCESS(f"{changed} product(s) renamed."))
