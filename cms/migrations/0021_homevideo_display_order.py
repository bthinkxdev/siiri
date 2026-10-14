from django.db import migrations, models


class Migration(migrations.Migration):
    """Show every active home video (not just the newest) in a configurable order."""

    dependencies = [
        ("cms", "0020_alter_homepagesection_section_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="homevideo",
            name="display_order",
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text="Lower numbers are shown first. Videos with the same number show oldest first.",
                verbose_name="Display order",
            ),
        ),
        migrations.AlterModelOptions(
            name="homevideo",
            options={
                "ordering": ["display_order", "id"],
                "verbose_name": "Home video",
                "verbose_name_plural": "Home videos",
            },
        ),
    ]
