"""Data layer for the cms app — models only, no business logic."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.icons import ICON_CHOICES
from core.models import SEOModel, TimeStampedModel


def validate_link_target(value: str) -> None:
    """Allow only site-relative paths or http(s) URLs so a link can never carry a script scheme."""
    if value.startswith("/") and not value.startswith("//"):
        return
    if value.lower().startswith(("http://", "https://")):
        return
    raise ValidationError("Enter a site path starting with / (e.g. /shop/) or a full http(s) URL.")


MAX_HOME_VIDEO_MB = 100


def validate_video_size(value) -> None:
    """Reject oversized uploads so a huge file cannot fill the disk or stall the storefront."""
    if value.size > MAX_HOME_VIDEO_MB * 1024 * 1024:
        raise ValidationError(f"Video must be {MAX_HOME_VIDEO_MB} MB or smaller.")


class HomepageSectionType(models.TextChoices):
    """Every homepage block type; add one enum value + one partial to extend."""

    HERO_SLIDER = "hero_slider", "Hero Slider"
    SHOP_BY_CATEGORY = "shop_by_category", "Shop by Category"
    FEATURED_PRODUCTS = "featured_products", "Featured Products"
    NEW_ARRIVALS = "new_arrivals", "New Arrivals"
    BEST_SELLERS = "best_sellers", "Best Sellers"
    FEATURED_BRANDS = "featured_brands", "Featured Brands"
    SUBSCRIPTION_BANNER = "subscription_banner", "Subscription Banner"
    MARKETING_FEATURES = "marketing_features", "Marketing Feature Cards"
    REVIEWS = "reviews", "Reviews"
    INSTAGRAM_GALLERY = "instagram_gallery", "Instagram Gallery"
    NEWSLETTER = "newsletter", "Newsletter"
    CATEGORY_PRODUCTS = "category_products", "Category Product Grids"
    PROMO_BANNERS = "promo_banners", "Promo Banners"
    SERVICE_STRIP = "service_strip", "Service Strip"
    WIDE_BANNER = "wide_banner", "Wide Banner"
    TESTIMONIALS = "testimonials", "Testimonials"
    VIDEO_SECTION = "video_section", "Video"
    MEMORIES = "memories", "Memories Gallery"
    PRODUCT_SPOTLIGHT = "product_spotlight", "Product Spotlight"


class PublishableModel(models.Model):
    """Mixin for scheduled publishing."""

    is_published = models.BooleanField(default=False, db_index=True, verbose_name="Is published")
    publish_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Publish at",
        help_text="Leave blank to publish immediately when is_published is checked.",
    )

    class Meta:
        abstract = True

    @property
    def is_live(self) -> bool:
        if not self.is_published:
            return False
        if self.publish_at and self.publish_at > timezone.now():
            return False
        return True


class HomepageSection(TimeStampedModel):
    """Configurable homepage section rendered via cms/sections/<type>.html partials."""

    section_type = models.CharField(
        max_length=40,
        choices=HomepageSectionType.choices,
        db_index=True,
        verbose_name="Section type",
    )
    title = models.CharField(max_length=200, blank=True, verbose_name="Title")
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Display order"
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")
    config = models.JSONField(default=dict, blank=True, verbose_name="Configuration")

    class Meta:
        verbose_name = "Homepage section"
        verbose_name_plural = "Homepage sections"
        ordering = ["display_order", "id"]
        indexes = [
            models.Index(
                fields=["is_active", "display_order"],
                name="cms_hp_section_active_ord_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_section_type_display()} (#{self.display_order})"


class HeroSlide(TimeStampedModel):
    """A single hero banner slide backed by an uploaded photo or video file."""

    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Title",
        help_text="Shown over the banner when set. Also used as media alt text.",
    )
    eyebrow = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Eyebrow",
        help_text="Optional small line shown above the title.",
    )
    subtitle = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Subtitle",
        help_text="Optional line shown below the title.",
    )
    cta_label = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Button label",
        help_text="Optional call-to-action button text. The button shows only when label and link are both set.",
    )
    cta_url = models.CharField(
        max_length=300,
        blank=True,
        validators=[validate_link_target],
        verbose_name="Button link",
        help_text="Optional call-to-action URL or path (e.g. /shop/).",
    )
    image = models.ImageField(
        upload_to="cms/hero/images/",
        blank=True,
        verbose_name="Photo",
        help_text=(
            "Photo slide, landscape about 2.56:1 (recommended 2400x940; 2:1 to 2.8:1 accepted, "
            "at least 1000px wide). Ignored when a video is uploaded. All slides should share one size."
        ),
    )
    video = models.FileField(
        upload_to="cms/hero/videos/",
        blank=True,
        verbose_name="Video",
        validators=[FileExtensionValidator(["mp4", "webm", "ogg", "mov"]), validate_video_size],
        help_text=(
            "Video slide (mp4 H.264 or webm), silent and looping. Keep it short and under about 15 MB for fast loading; "
            "the frame is about 2.5:1 on desktop, so keep the subject centred. Takes priority over the photo."
        ),
    )
    poster = models.ImageField(
        upload_to="cms/hero/posters/",
        blank=True,
        verbose_name="Video poster",
        help_text="Still image shown while the video loads.",
    )
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Display order"
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "Hero slide"
        verbose_name_plural = "Hero slides"
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="cms_hero_active_order_idx"),
        ]

    def __str__(self) -> str:
        return self.title or f"Hero slide #{self.pk}"

    @property
    def media_type(self) -> str:
        return "video" if self.video else "image"

    @property
    def media_src(self) -> str:
        if self.video:
            return self.video.url
        if self.image:
            return self.image.url
        return ""

    @property
    def poster_src(self) -> str:
        return self.poster.url if self.poster else ""


class PromoBannerStyle(models.TextChoices):
    TILE = "tile", "Tile (two per row)"
    WIDE = "wide", "Wide closing banner"


class PromoBanner(TimeStampedModel):
    """A homepage promo tile or full-width closing banner (photo + editorial text + button)."""

    style = models.CharField(
        max_length=10,
        choices=PromoBannerStyle.choices,
        default=PromoBannerStyle.TILE,
        db_index=True,
        verbose_name="Style",
        help_text="Tile: shown two per row in the Promo Banners section. Wide: the first active one fills the Wide Banner section.",
    )
    eyebrow = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Eyebrow",
        help_text="Optional small line shown above the title.",
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Title",
        help_text="Main heading. Also used as the image alt text.",
    )
    subtitle = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Subtitle",
        help_text="Optional line shown below the title.",
    )
    cta_label = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Button label",
        help_text="The button shows only when label and link are both set.",
    )
    cta_url = models.CharField(
        max_length=300,
        blank=True,
        validators=[validate_link_target],
        verbose_name="Button link",
        help_text="Site path (e.g. /shop/) or full http(s) URL.",
    )
    image = models.ImageField(
        upload_to="cms/promo/",
        blank=True,
        verbose_name="Photo",
        help_text=(
            "Background photo. Tile: about 1200x600 (2:1). Wide: about 2400x480 (5:1). "
            "Without a photo a solid maroon panel is shown."
        ),
    )
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Display order"
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "Promo banner"
        verbose_name_plural = "Promo banners"
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="cms_promo_active_order_idx"),
        ]

    def __str__(self) -> str:
        return self.title or f"Promo banner #{self.pk}"


class ServiceHighlight(TimeStampedModel):
    """One item of the homepage service strip (line icon + short label)."""

    icon = models.CharField(
        max_length=20,
        choices=ICON_CHOICES,
        default="star",
        verbose_name="Icon",
    )
    label = models.CharField(
        max_length=80,
        verbose_name="Label",
        help_text="Short text; it wraps onto two lines (e.g. two words per line).",
    )
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Display order"
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "Service highlight"
        verbose_name_plural = "Service highlights"
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="cms_service_active_order_idx"),
        ]

    def __str__(self) -> str:
        return self.label


class Testimonial(TimeStampedModel):
    """A customer testimonial shown in the homepage testimonials section."""

    name = models.CharField(max_length=100, verbose_name="Customer name")
    location = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Location / description",
        help_text="Optional, shown under the name (e.g. a city).",
    )
    quote = models.TextField(
        max_length=400,
        verbose_name="Testimonial",
        help_text="The customer's words (up to 400 characters).",
    )
    photo = models.ImageField(
        upload_to="cms/testimonials/",
        blank=True,
        verbose_name="Profile photo",
        help_text="Square photo works best (at least 200x200). Without one, the customer's initial is shown.",
    )
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Star rating",
        help_text="Optional, 1 to 5. Stars are hidden when blank.",
    )
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Display order"
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "Testimonial"
        verbose_name_plural = "Testimonials"
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="cms_testimonial_active_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class HomeVideo(TimeStampedModel):
    """The homepage video section: one uploaded video with an editable heading."""

    title = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Section title",
        help_text="Heading shown above the video.",
    )
    subtitle = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Subtitle",
        help_text="Optional line shown under the heading.",
    )
    video = models.FileField(
        upload_to="cms/video/",
        verbose_name="Video",
        validators=[FileExtensionValidator(["mp4", "webm", "ogg", "mov"]), validate_video_size],
        help_text=(
            f"mp4 or webm, up to {MAX_HOME_VIDEO_MB} MB. mp4 (H.264) plays everywhere. "
            "It plays automatically, silent and looping, with no controls."
        ),
    )
    poster = models.ImageField(
        upload_to="cms/video/posters/",
        blank=True,
        verbose_name="Cover image",
        help_text="Still image shown before the video plays (recommended).",
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")

    class Meta:
        ordering = ["-updated_at", "-id"]
        verbose_name = "Home video"
        verbose_name_plural = "Home videos"

    def __str__(self) -> str:
        return self.title or f"Home video #{self.pk}"


class MemoryPhoto(TimeStampedModel):
    """A photo in the homepage memories gallery (customer moments in the shop)."""

    image = models.ImageField(
        upload_to="cms/memories/",
        verbose_name="Photo",
        help_text="Portrait photo works best (about 4:5, at least 600px wide). Resize very large photos before uploading.",
    )
    caption = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Caption",
        help_text="Optional short text shown over the photo (e.g. a name).",
    )
    display_order = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Display order"
    )
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="Is active")

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "Memory photo"
        verbose_name_plural = "Memory photos"
        indexes = [
            models.Index(fields=["is_active", "display_order"], name="cms_memory_active_order_idx"),
        ]

    def __str__(self) -> str:
        return self.caption or f"Memory photo #{self.pk}"


class BlogPost(TimeStampedModel, SEOModel, PublishableModel):
    """CMS blog article."""

    title = models.CharField(max_length=255)
    slug = SEOModel.slug_field()
    body = models.TextField()
    excerpt = models.TextField(blank=True)

    class Meta:
        ordering = ["-publish_at", "-created_at"]
        verbose_name = "Blog post"
        verbose_name_plural = "Blog posts"

    def get_absolute_url(self) -> str:
        # There's no individual blog-post detail page/route in this codebase yet
        # (core.urls only has a "blog" list view) — points at the list page so the
        # sitemap doesn't crash. Give each post its own URL once a detail view exists.
        from django.urls import reverse

        return reverse("core:blog")


class Page(TimeStampedModel, SEOModel, PublishableModel):
    """Static CMS page (About, Contact, etc.)."""

    title = models.CharField(max_length=255)
    slug = SEOModel.slug_field()
    body = models.TextField()

    class Meta:
        ordering = ["title"]
        verbose_name = "Page"
        verbose_name_plural = "Pages"

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("core:page", kwargs={"slug": self.slug})


class FAQItem(TimeStampedModel, PublishableModel):
    """Frequently asked question."""

    question = models.CharField(max_length=255)
    answer = models.TextField()
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name = "FAQ item"
        verbose_name_plural = "FAQ items"


class PolicyDocument(TimeStampedModel, SEOModel, PublishableModel):
    """Legal/policy document (privacy, terms, etc.)."""

    title = models.CharField(max_length=255)
    slug = SEOModel.slug_field()
    body = models.TextField()
    policy_type = models.CharField(max_length=40, db_index=True, default="general")

    class Meta:
        ordering = ["title"]
        verbose_name = "Policy document"
        verbose_name_plural = "Policy documents"
