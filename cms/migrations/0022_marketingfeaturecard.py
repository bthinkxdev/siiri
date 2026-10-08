import cms.models
from django.db import migrations, models


class Migration(migrations.Migration):
    """Marketing feature cards managed from their own dashboard page (like Memories)."""

    dependencies = [
        ("cms", "0021_homevideo_display_order"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketingFeatureCard",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        help_text="Timestamp when this record was first created.",
                        verbose_name="Created at",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        db_index=True,
                        help_text="Timestamp when this record was last modified.",
                        verbose_name="Updated at",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        help_text="Short text shown on the card (e.g. Bridal Sarees).",
                        max_length=120,
                        verbose_name="Title",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        help_text="Landscape image works best (about 5:3, at least 600px wide).",
                        upload_to="cms/feature_cards/",
                        verbose_name="Image",
                    ),
                ),
                (
                    "link_url",
                    models.CharField(
                        blank=True,
                        help_text="Where the card goes when clicked: a site path like /shop/ or a full https:// URL. Optional.",
                        max_length=300,
                        validators=[cms.models.validate_link_target],
                        verbose_name="Link",
                    ),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(
                        db_index=True, default=0, verbose_name="Display order"
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(db_index=True, default=True, verbose_name="Is active"),
                ),
            ],
            options={
                "verbose_name": "Marketing feature card",
                "verbose_name_plural": "Marketing feature cards",
                "ordering": ["display_order", "id"],
                "indexes": [
                    models.Index(
                        fields=["is_active", "display_order"], name="cms_featcard_active_order_idx"
                    )
                ],
            },
        ),
    ]
