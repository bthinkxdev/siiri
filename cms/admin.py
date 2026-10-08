"""Django admin registrations for the cms app."""

from __future__ import annotations

from django.contrib import admin

from cms.forms import HomepageSectionAdminForm
from cms.models import (
    BlogPost,
    FAQItem,
    HeroSlide,
    PromoBanner,
    HomepageSection,
    Page,
    PolicyDocument,
    ServiceHighlight,
    Testimonial,
    HomeVideo,
    MemoryPhoto,
    MarketingFeatureCard,
)


@admin.register(HomepageSection)
class HomepageSectionAdmin(admin.ModelAdmin):
    """
    Homepage builder admin with structured per-type config forms.

    Ordering uses list_editable display_order (no extra dependency) — admins
    set numeric order and drag-sort can be added later via django-admin-sortable2
    if product owners need visual reordering at scale.
    """

    form = HomepageSectionAdminForm
    list_display = ("section_type", "title", "display_order", "is_active", "updated_at")
    list_filter = ("section_type", "is_active")
    search_fields = ("title", "section_type")
    ordering = ("display_order", "id")
    list_editable = ("display_order", "is_active")
    fieldsets = ((None, {"fields": ("section_type", "title", "display_order", "is_active")}),)


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    """Upload photo or video hero slides; ordering via list_editable display_order."""

    list_display = ("__str__", "media_type", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    list_editable = ("display_order", "is_active")
    ordering = ("display_order", "id")
    fields = (
        "eyebrow",
        "title",
        "subtitle",
        "cta_label",
        "cta_url",
        "image",
        "video",
        "poster",
        "display_order",
        "is_active",
    )

    @admin.display(description="Media")
    def media_type(self, obj: HeroSlide) -> str:
        return obj.media_type


@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    """Homepage promo tiles; ordering via list_editable display_order."""

    list_display = ("__str__", "style", "display_order", "is_active", "updated_at")
    list_filter = ("style", "is_active")
    list_editable = ("display_order", "is_active")
    ordering = ("display_order", "id")
    fields = (
        "style",
        "eyebrow",
        "title",
        "subtitle",
        "cta_label",
        "cta_url",
        "image",
        "display_order",
        "is_active",
    )


@admin.register(ServiceHighlight)
class ServiceHighlightAdmin(admin.ModelAdmin):
    """Service strip items; ordering via list_editable display_order."""

    list_display = ("label", "icon", "display_order", "is_active")
    list_filter = ("is_active",)
    list_editable = ("display_order", "is_active")
    ordering = ("display_order", "id")
    fields = ("icon", "label", "display_order", "is_active")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    """Homepage testimonials; ordering via list_editable display_order."""

    list_display = ("name", "location", "rating", "display_order", "is_active")
    list_filter = ("is_active",)
    list_editable = ("display_order", "is_active")
    ordering = ("display_order", "id")
    fields = ("name", "location", "quote", "photo", "rating", "display_order", "is_active")


@admin.register(HomeVideo)
class HomeVideoAdmin(admin.ModelAdmin):
    """Homepage videos; every active one is shown, ordered by display_order."""

    list_display = ("__str__", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    fields = ("title", "subtitle", "video", "poster", "display_order", "is_active")


@admin.register(MemoryPhoto)
class MemoryPhotoAdmin(admin.ModelAdmin):
    """Memories gallery photos; ordering via list_editable display_order."""

    list_display = ("__str__", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    list_editable = ("display_order", "is_active")
    ordering = ("display_order", "id")
    fields = ("image", "caption", "display_order", "is_active")


@admin.register(MarketingFeatureCard)
class MarketingFeatureCardAdmin(admin.ModelAdmin):
    """Homepage marketing feature cards; ordering via list_editable display_order."""

    list_display = ("__str__", "link_url", "display_order", "is_active", "updated_at")
    list_filter = ("is_active",)
    list_editable = ("display_order", "is_active")
    ordering = ("display_order", "id")
    fields = ("title", "image", "link_url", "display_order", "is_active")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "publish_at")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "publish_at")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug")


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ("question", "display_order", "is_published")
    list_editable = ("display_order", "is_published")
    ordering = ("display_order",)


@admin.register(PolicyDocument)
class PolicyDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "policy_type", "slug", "is_published")
    prepopulated_fields = {"slug": ("title",)}
    list_filter = ("policy_type", "is_published")
