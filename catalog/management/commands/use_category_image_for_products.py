"""Replace each product's photos with its category's image, as a placeholder (idempotent)."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Product, ProductImage


class Command(BaseCommand):
    help = (
        "Delete all existing ProductImage rows and replace each product's photo with "
        "its own category's og_image, as a placeholder until real product photos exist."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="Report changes without saving.")

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]

        products = list(
            Product.objects.select_related("category").prefetch_related("images").all()
        )
        missing_category_image = [p for p in products if not p.category or not p.category.og_image]
        for p in missing_category_image:
            self.stdout.write(self.style.WARNING(f"[{p.id}] {p.name!r}: category has no image, skipping."))

        eligible = [p for p in products if p.category and p.category.og_image]
        old_image_count = sum(p.images.count() for p in eligible)

        self.stdout.write(f"{len(eligible)} product(s) to update, {old_image_count} existing image row(s) to remove.")

        if dry_run:
            for p in eligible[:5]:
                self.stdout.write(f"[{p.id}] {p.name!r} -> {p.category.og_image.name!r}")
            if len(eligible) > 5:
                self.stdout.write(f"... and {len(eligible) - 5} more.")
            self.stdout.write("Dry run: nothing saved.")
            return

        with transaction.atomic():
            ProductImage.objects.filter(product__in=eligible).delete()
            ProductImage.objects.bulk_create(
                ProductImage(
                    product=p,
                    image=p.category.og_image.name,
                    alt_text=p.name,
                    display_order=0,
                    is_primary=True,
                )
                for p in eligible
            )

        self.stdout.write(self.style.SUCCESS(f"{len(eligible)} product(s) updated."))
