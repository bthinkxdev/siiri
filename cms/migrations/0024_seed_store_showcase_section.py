from django.core.cache import cache
from django.db import migrations


def seed_store_showcase(apps, schema_editor) -> None:
    HomepageSection = apps.get_model("cms", "HomepageSection")
    if HomepageSection.objects.filter(section_type="store_showcase").exists():
        return
    max_order = HomepageSection.objects.order_by("-display_order").values_list(
        "display_order", flat=True
    ).first() or 0
    HomepageSection.objects.create(
        section_type="store_showcase",
        title="",
        is_active=True,
        display_order=max_order + 10,
        config={},
    )
    #migrations use historical models, so the post_save signal that normally
    #refreshes the homepage cache doesn't fire here — clear it directly so
    #the new section shows up immediately instead of waiting out the TTL.
    cache.delete("cms:homepage_sections:active:v1")


def noop(apps, schema_editor) -> None:
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0023_alter_homepagesection_section_type"),
    ]

    operations = [
        migrations.RunPython(seed_store_showcase, noop),
    ]
