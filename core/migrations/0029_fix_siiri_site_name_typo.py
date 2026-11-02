from django.db import migrations


def fix_site_name(apps, schema_editor) -> None:
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.filter(site_name="SIRI COUTURE").update(site_name="SIIRI COUTURE")


def revert_site_name(apps, schema_editor) -> None:
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.filter(site_name="SIIRI COUTURE").update(site_name="SIRI COUTURE")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_alter_sitesettings_site_name"),
    ]

    operations = [
        migrations.RunPython(fix_site_name, revert_site_name),
    ]
