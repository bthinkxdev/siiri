"""Read-only query functions for the cms app; views must not call the ORM directly."""

from __future__ import annotations

from typing import Any

from django.core.cache import cache

HOMEPAGE_SECTIONS_CACHE_KEY = "cms:homepage_sections:active:v1"
HOMEPAGE_SECTIONS_CACHE_TTL = 300


def get_active_homepage_sections() -> list[dict[str, Any]]:
    """
    Return ordered active homepage sections from the Redis-cached snapshot.

    Query guarantee: 0 DB queries on cache hit. On cache miss the Celery task
    `cms.tasks.refresh_homepage_cache` repopulates the snapshot (1 SELECT).

    Cache key: cms:homepage_sections:active:v1
    TTL: 300 seconds (HOMEPAGE_SECTIONS_CACHE_TTL)

    Returns:
        List of section dicts with keys: id, section_type, title, display_order, config.
    """
    cached = cache.get(HOMEPAGE_SECTIONS_CACHE_KEY)
    if cached is not None:
        return cached

    from cms.services import build_homepage_sections_snapshot

    snapshot = build_homepage_sections_snapshot()
    try:
        cache.set(HOMEPAGE_SECTIONS_CACHE_KEY, snapshot, timeout=HOMEPAGE_SECTIONS_CACHE_TTL)
    except Exception:
        pass
    return snapshot


def get_hero_slides() -> list[dict[str, Any]]:
    """
    Return active hero slides (uploaded photos/videos) ordered for display.

    Query guarantee: exactly 1 SELECT on cms_heroslide.

    Returns:
        List of slide dicts with keys: type, src, poster, title, eyebrow, subtitle, cta_label, cta_url.
        Slides without any media file are skipped.
    """
    from cms.models import HeroSlide

    slides: list[dict[str, Any]] = []
    for slide in HeroSlide.objects.filter(is_active=True).order_by("display_order", "id"):
        src = slide.media_src
        if not src:
            continue
        slides.append(
            {
                "type": slide.media_type,
                "src": src,
                "poster": slide.poster_src,
                "mime": _video_mime(src) if slide.media_type == "video" else "",
                "title": slide.title,
                "eyebrow": slide.eyebrow,
                "subtitle": slide.subtitle,
                "cta_label": slide.cta_label,
                "cta_url": slide.cta_url,
            }
        )
    return slides


def get_promo_banners(*, style: str = "tile", limit: int | None = None) -> list[dict[str, Any]]:
    """
    Return active promo banners of one style in display order.

    Query guarantee: exactly 1 SELECT on cms_promobanner.

    Returns:
        List of dicts with keys: image, title, eyebrow, subtitle, cta_label, cta_url.
        Banners with neither a title nor a photo are skipped.
    """
    from cms.models import PromoBanner

    banners = [
        {
            "image": banner.image.url if banner.image else "",
            "title": banner.title,
            "eyebrow": banner.eyebrow,
            "subtitle": banner.subtitle,
            "cta_label": banner.cta_label,
            "cta_url": banner.cta_url,
        }
        for banner in PromoBanner.objects.filter(is_active=True, style=style).order_by(
            "display_order", "id"
        )
        if banner.title or banner.image
    ]
    return banners[:limit] if limit else banners


def get_service_highlights() -> list[dict[str, str]]:
    """
    Return active service-strip items in display order.

    Query guarantee: exactly 1 SELECT on cms_servicehighlight.

    Returns:
        List of dicts with keys: icon, label.
    """
    from cms.models import ServiceHighlight

    return [
        {"icon": item.icon, "label": item.label}
        for item in ServiceHighlight.objects.filter(is_active=True).order_by("display_order", "id")
    ]


def _video_mime(path: str) -> str:
    import os

    return _VIDEO_MIME_TYPES.get(os.path.splitext(path)[1].lower(), "video/mp4")


_VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".ogg": "video/ogg",
    ".mov": "video/quicktime",
}


def get_testimonials(limit: int = 6) -> list[dict[str, Any]]:
    """
    Return active testimonials in display order.

    Query guarantee: exactly 1 SELECT on cms_testimonial.

    Returns:
        List of dicts with keys: name, location, quote, photo (URL or ""), rating (1-5 or None).
    """
    from cms.models import Testimonial

    return [
        {
            "name": item.name,
            "location": item.location,
            "quote": item.quote,
            "photo": item.photo.url if item.photo else "",
            "rating": item.rating,
        }
        for item in Testimonial.objects.filter(is_active=True).order_by("display_order", "id")[:limit]
    ]


def get_home_videos() -> list[dict[str, Any]]:
    """
    Return every active homepage video, ordered by display_order then id (oldest first).

    Query guarantee: exactly 1 SELECT on cms_homevideo.

    Returns:
        List of dicts with keys: title, subtitle, src, mime, poster (URL or "").
    """
    from cms.models import HomeVideo

    return [
        {
            "title": video.title,
            "subtitle": video.subtitle,
            "src": video.video.url,
            "mime": _video_mime(video.video.name),
            "poster": video.poster.url if video.poster else "",
        }
        for video in HomeVideo.objects.filter(is_active=True).exclude(video="").order_by("display_order", "id")
    ]


def get_home_video() -> dict[str, Any] | None:
    """Return the first homepage video in display order, or None (kept for existing callers)."""
    videos = get_home_videos()
    return videos[0] if videos else None


def get_memory_photos(limit: int = 12) -> list[dict[str, str]]:
    """
    Return active memories-gallery photos in display order.

    Query guarantee: exactly 1 SELECT on cms_memoryphoto.

    Returns:
        List of dicts with keys: image (URL), caption.
    """
    from cms.models import MemoryPhoto

    return [
        {"image": photo.image.url, "caption": photo.caption}
        for photo in MemoryPhoto.objects.filter(is_active=True).exclude(image="").order_by("display_order", "id")[:limit]
    ]


def get_marketing_feature_cards(limit: int = 12) -> list[dict[str, str]]:

    from cms.models import MarketingFeatureCard

    return [
        {"title": card.title, "url": card.link_url, "image": card.image.url}
        for card in MarketingFeatureCard.objects.filter(is_active=True)
        .exclude(image="")
        .order_by("display_order", "id")[:limit]
    ]
