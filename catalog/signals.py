"""Cache invalidation signals for catalog models."""

from __future__ import annotations

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from catalog.models import Category, Product
from catalog.selectors import invalidate_category_tree_cache


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def category_changed(sender, instance: Category, **kwargs) -> None:
    invalidate_category_tree_cache()


@receiver(post_save, sender=Product)
def product_spotlight_changed(sender, instance: Product, **kwargs) -> None:
    """Keep a product's homepage-spotlight HomepageSection row in sync with its flag."""
    from cms.models import HomepageSection, HomepageSectionType
    from cms.services import refresh_homepage_cache

    existing = None
    for section in HomepageSection.objects.filter(section_type=HomepageSectionType.PRODUCT_SPOTLIGHT):
        if (section.config or {}).get("product_id") == instance.pk:
            existing = section
            break

    if existing is None:
        if not instance.show_home_spotlight:
            return
        max_order = HomepageSection.objects.aggregate(models.Max("display_order"))["display_order__max"] or 0
        HomepageSection.objects.create(
            section_type=HomepageSectionType.PRODUCT_SPOTLIGHT,
            title=instance.name,
            display_order=max_order + 1,
            is_active=True,
            config={"product_id": instance.pk},
        )
    else:
        update_fields = []
        if existing.is_active != instance.show_home_spotlight:
            existing.is_active = instance.show_home_spotlight
            update_fields.append("is_active")
        if existing.title != instance.name:
            existing.title = instance.name
            update_fields.append("title")
        if not update_fields:
            return
        existing.save(update_fields=update_fields)

    refresh_homepage_cache()
