from django.db import migrations


def rename_site(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    # Only replaces the old seeded brand name; any custom name is left untouched.
    SiteSettings.objects.filter(pk=1, site_name__iexact="yarn guy").update(site_name="SIRI COUTURE")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_sitesettings_feature_switches"),
    ]

    operations = [
        migrations.RunPython(rename_site, migrations.RunPython.noop),
    ]
