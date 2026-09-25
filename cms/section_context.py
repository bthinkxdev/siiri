"""Homepage section context builders — delegates to catalog selectors, never ORM."""

from __future__ import annotations

from typing import Any

from catalog.selectors import (
    get_featured_brands,
    get_homepage_product_rails,
    get_products_for_section_config,
    get_recent_approved_reviews,
    get_root_categories,
)
from cms.selectors import (
    get_home_video,
    get_hero_slides,
    get_memory_photos,
    get_promo_banners,
    get_service_highlights,
    get_testimonials,
)


def build_section_context(
    *,
    section: dict[str, Any],
    product_rails: dict[str, list] | None = None,
    request: Any = None,
) -> dict[str, Any]:
    """
    Dispatch section_type to the appropriate data source.

    Every section pulls live catalog/cms config data — nothing is hardcoded in templates.
    `request` is optional and only used by sections that need per-visitor state
    (e.g. product_spotlight's cart/wishlist status); every other section ignores it.
    """
    section_type = section["section_type"]
    config = section.get("config") or {}
    base = {
        "section": section,
        "title": section.get("title", ""),
        "config": config,
    }

    builders = {
        "hero_slider": _hero_slider,
        "shop_by_occasion": _empty,
        "shop_by_recipient": _empty,
        "shop_by_category": _shop_by_category,
        "featured_products": _featured,
        "new_arrivals": _new_arrivals,
        "best_sellers": _best_sellers,
        "featured_brands": _featured_brands,
        "corporate_gifts_banner": _empty,
        "subscription_banner": _banner,
        "marketing_features": _marketing_features,
        "reviews": _reviews,
        "instagram_gallery": _instagram,
        "newsletter": _newsletter,
        "category_products": _category_products,
        "promo_banners": _promo_banners,
        "testimonials": _testimonials,
        "video_section": _video_section,
        "memories": _memories,
        "service_strip": _service_strip,
        "wide_banner": _wide_banner,
        "product_spotlight": _product_spotlight,
    }
    builder = builders.get(section_type, _empty)
    if section_type in ("featured_products", "best_sellers", "new_arrivals"):
        base.update(builder(config, product_rails=product_rails))
    elif section_type == "product_spotlight":
        base.update(builder(config, request=request))
    else:
        base.update(builder(config))
    return base


def _rails(product_rails: dict[str, list] | None, key: str) -> list:
    if product_rails is not None:
        return product_rails.get(key, [])
    return get_homepage_product_rails().get(key, [])


def _category_products(config: dict[str, Any]) -> dict[str, Any]:
    from catalog.models import Category
    from catalog.selectors import get_products_by_category_slug
    
    slug_val = config.get("category_slug", "all")
    sections = []
    
    if slug_val == "all":
        roots = Category.objects.filter(
            is_active=True, show_on_homepage=True, parent__isnull=True
        ).order_by("display_order")
        for cat in roots:
            prods = get_products_by_category_slug(cat.slug, limit=100) # fetch effectively all products
            if prods:
                sections.append({"category": cat, "products": prods})
    else:
        if isinstance(slug_val, str):
            slugs = [s.strip() for s in slug_val.split(",") if s.strip()]
        else:
            slugs = slug_val

        for s in slugs:
            cat = Category.objects.filter(slug=s, is_active=True).first()
            if cat:
                prods = get_products_by_category_slug(s, limit=100)
                if prods:
                    sections.append({"category": cat, "products": prods})
                
    return {"category_sections": sections}


def _promo_banners(config: dict[str, Any]) -> dict[str, Any]:
    return {"banners": get_promo_banners(style="tile")}


def _wide_banner(config: dict[str, Any]) -> dict[str, Any]:
    banners = get_promo_banners(style="wide", limit=1)
    return {"banner": banners[0] if banners else None}


def _service_strip(config: dict[str, Any]) -> dict[str, Any]:
    return {"items": get_service_highlights()}


def _testimonials(config: dict[str, Any]) -> dict[str, Any]:
    return {"testimonials": get_testimonials()}


def _memories(config: dict[str, Any]) -> dict[str, Any]:
    return {"photos": get_memory_photos(), "subtitle": config.get("subtitle", "")}


def _video_section(config: dict[str, Any]) -> dict[str, Any]:
    return {"video": get_home_video()}


def _hero_slider(config: dict[str, Any]) -> dict[str, Any]:
    """Prefer uploaded photo/video slides; fall back to legacy URL-based config."""
    slides = get_hero_slides()
    if slides:
        return {"slides": slides, "has_video": any(slide["type"] == "video" for slide in slides)}

    legacy_slides = config.get("slides") or []
    fallback = [
        {
            "type": "image",
            "src": slide.get("image") or slide.get("src") or "",
            "poster": slide.get("poster") or "",
            "title": slide.get("title") or "",
        }
        for slide in legacy_slides
        if isinstance(slide, dict) and (slide.get("image") or slide.get("src"))
    ]
    return {"slides": fallback}


def _shop_by_occasion(config: dict[str, Any]) -> dict[str, Any]:
    return {}


def _shop_by_recipient(config: dict[str, Any]) -> dict[str, Any]:
    return {}


def _shop_by_category(config: dict[str, Any]) -> dict[str, Any]:
    return {"categories": get_root_categories(category_ids=None)}


def _featured(
    config: dict[str, Any], product_rails: dict[str, list] | None = None
) -> dict[str, Any]:
    return {"products": _rails(product_rails, "featured")}


def _new_arrivals(
    config: dict[str, Any], product_rails: dict[str, list] | None = None
) -> dict[str, Any]:
    return {"products": _rails(product_rails, "new_arrivals")}


def _best_sellers(
    config: dict[str, Any], product_rails: dict[str, list] | None = None
) -> dict[str, Any]:
    return {"products": _rails(product_rails, "bestsellers")}


def _featured_brands(config: dict[str, Any]) -> dict[str, Any]:
    brand_ids = config.get("brand_ids")
    return {"brands": get_featured_brands(brand_ids=brand_ids)}


def _banner(config: dict[str, Any]) -> dict[str, Any]:
    return {"banner": config}


def _marketing_features(config: dict[str, Any]) -> dict[str, Any]:
    return {"cards": config.get("cards", [])}


def _reviews(config: dict[str, Any]) -> dict[str, Any]:
    limit = config.get("limit", 6)
    return {"reviews": get_recent_approved_reviews(limit=limit)}


def _instagram(config: dict[str, Any]) -> dict[str, Any]:
    return {"images": config.get("images", [])}


def _newsletter(config: dict[str, Any]) -> dict[str, Any]:
    return {"placeholder": config.get("placeholder", "")}


def _empty(config: dict[str, Any]) -> dict[str, Any]:
    return {}


def _product_spotlight(config: dict[str, Any], request: Any = None) -> dict[str, Any]:
    """Full PDP-style preview of one flagged product. Mirrors catalog.views.pdp_view's context build."""
    from catalog.models import Product
    from catalog.selectors import get_product_detail, get_variant_price

    product_id = config.get("product_id")
    if not product_id:
        return {}

    slug = Product.objects.filter(pk=product_id, is_active=True).values_list("slug", flat=True).first()
    if not slug:
        return {}

    product = get_product_detail(slug=slug)
    if product is None:
        return {}

    target_variant = product.display_variant
    is_in_cart = False
    is_in_wishlist = False

    if request is not None:
        from cart.models import CartItem
        from cart.selectors import get_cart_for_request

        cart = get_cart_for_request(request=request)
        if cart:
            variant_filter = {"variant": target_variant} if target_variant else {"variant__isnull": True}
            is_in_cart = CartItem.objects.filter(cart=cart, product=product, **variant_filter).exists()

        from accounts.models import WishlistItem
        from accounts.subscription_services import get_or_create_wishlist

        wishlist = get_or_create_wishlist(request=request)
        is_in_wishlist = WishlistItem.objects.filter(wishlist=wishlist, product_id=product.pk).exists()

    price_data = get_variant_price(
        product_id=product.pk,
        variant_id=target_variant.pk if target_variant else None,
        user=getattr(request, "user", None),
        quantity=1,
    )

    from cms.selectors import get_service_highlights

    return {
        "product": product,
        "price_data": price_data,
        "is_in_cart": is_in_cart,
        "is_in_wishlist": is_in_wishlist,
        "selected_variant_id": target_variant.pk if target_variant else "",
        "target_variant": target_variant,
        "service_highlights": get_service_highlights(),
    }
