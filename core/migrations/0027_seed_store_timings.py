from django.db import migrations


def seed_store_timings(apps, schema_editor) -> None:
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.filter(pk=1).update(store_timings="Monday – Sunday: 10:00 AM – 8:00 PM")


def noop(apps, schema_editor) -> None:
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_sitesettings_store_timings"),
    ]

    operations = [
        migrations.RunPython(seed_store_timings, noop),
    ]
