"""CMS management: homepage sections, hero slides, blog, pages, FAQs, policies."""

from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from dashboard.access import dashboard_required

from cms.models import BlogPost, FAQItem, HeroSlide, HomepageSection, Page, PolicyDocument, PromoBanner, ServiceHighlight, Testimonial, HomeVideo, MemoryPhoto
from dashboard import forms
from dashboard.views.base import (
    DashboardCreateView,
    DashboardDeleteView,
    DashboardListView,
    DashboardUpdateView,
)


@dashboard_required
@require_POST
def homepagesection_reorder(request: HttpRequest) -> HttpResponse:
    """
    Persist a drag-and-drop ordering of the homepage sections.

    Body: {"order": [id, id, ...]} — must list every existing section exactly once, so a stale page
    (a section was added/removed elsewhere) is rejected instead of silently mis-ordering the storefront.
    """
    try:
        payload = json.loads(request.body or b"{}")
        order = payload["order"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "Invalid payload."}, status=400)
    if (
        not isinstance(order, list)
        or not order
        or any(isinstance(pk, bool) or not isinstance(pk, int) for pk in order)
        or len(set(order)) != len(order)
    ):
        return JsonResponse({"error": "Invalid payload."}, status=400)

    with transaction.atomic():
        sections = list(HomepageSection.objects.select_for_update().filter(pk__in=order))
        if len(sections) != len(order) or HomepageSection.objects.count() != len(order):
            return JsonResponse({"error": "The section list has changed. Reload the page."}, status=409)
        position = {pk: index for index, pk in enumerate(order)}
        for section in sections:
            section.display_order = position[section.pk]
        HomepageSection.objects.bulk_update(sections, ["display_order"])

    from cms.services import refresh_homepage_cache

    refresh_homepage_cache()
    return JsonResponse({"ok": True})


class HomepageSectionListView(DashboardListView):
    model = HomepageSection
    nav_section = "homepage"
    url_basename = "homepagesection"
    singular_name = "Section"
    plural_name = "Homepage Sections"
    paginate_by = None  # drag-and-drop ordering needs every section on one page
    reorder_url_name = "dashboard:homepagesection-reorder"
    columns = [
        {"label": "Type", "name": "get_section_type_display"},
        {"label": "Title", "name": "title"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class HomepageSectionCreateView(DashboardCreateView):
    model = HomepageSection
    form_class = forms.HomepageSectionForm
    nav_section = "homepage"
    url_basename = "homepagesection"
    singular_name = "Section"


class HomepageSectionUpdateView(DashboardUpdateView):
    model = HomepageSection
    form_class = forms.HomepageSectionForm
    nav_section = "homepage"
    url_basename = "homepagesection"
    singular_name = "Section"


class HomepageSectionDeleteView(DashboardDeleteView):
    model = HomepageSection
    nav_section = "homepage"
    url_basename = "homepagesection"
    singular_name = "Section"


class PromoBannerListView(DashboardListView):
    model = PromoBanner
    nav_section = "promobanners"
    url_basename = "promobanner"
    singular_name = "Promo Banner"
    plural_name = "Promo Banners"
    columns = [
        {"label": "Image", "name": "image", "type": "image"},
        {"label": "Title", "name": "title"},
        {"label": "Style", "name": "get_style_display"},
        {"label": "Order", "name": "display_order"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class PromoBannerCreateView(DashboardCreateView):
    model = PromoBanner
    form_class = forms.PromoBannerForm
    nav_section = "promobanners"
    url_basename = "promobanner"
    singular_name = "Promo Banner"


class PromoBannerUpdateView(DashboardUpdateView):
    model = PromoBanner
    form_class = forms.PromoBannerForm
    nav_section = "promobanners"
    url_basename = "promobanner"
    singular_name = "Promo Banner"


class PromoBannerDeleteView(DashboardDeleteView):
    model = PromoBanner
    nav_section = "promobanners"
    url_basename = "promobanner"
    singular_name = "Promo Banner"


class TestimonialListView(DashboardListView):
    model = Testimonial
    nav_section = "testimonials"
    url_basename = "testimonial"
    singular_name = "Testimonial"
    plural_name = "Testimonials"
    columns = [
        {"label": "Photo", "name": "photo", "type": "image"},
        {"label": "Name", "name": "name"},
        {"label": "Rating", "name": "rating"},
        {"label": "Order", "name": "display_order"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class TestimonialCreateView(DashboardCreateView):
    model = Testimonial
    form_class = forms.TestimonialForm
    nav_section = "testimonials"
    url_basename = "testimonial"
    singular_name = "Testimonial"


class TestimonialUpdateView(DashboardUpdateView):
    model = Testimonial
    form_class = forms.TestimonialForm
    nav_section = "testimonials"
    url_basename = "testimonial"
    singular_name = "Testimonial"


class TestimonialDeleteView(DashboardDeleteView):
    model = Testimonial
    nav_section = "testimonials"
    url_basename = "testimonial"
    singular_name = "Testimonial"


class MemoryPhotoListView(DashboardListView):
    model = MemoryPhoto
    nav_section = "memories"
    url_basename = "memoryphoto"
    singular_name = "Memory Photo"
    plural_name = "Memories"
    columns = [
        {"label": "Photo", "name": "image", "type": "image"},
        {"label": "Caption", "name": "caption"},
        {"label": "Order", "name": "display_order"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class MemoryPhotoCreateView(DashboardCreateView):
    model = MemoryPhoto
    form_class = forms.MemoryPhotoForm
    nav_section = "memories"
    url_basename = "memoryphoto"
    singular_name = "Memory Photo"


class MemoryPhotoUpdateView(DashboardUpdateView):
    model = MemoryPhoto
    form_class = forms.MemoryPhotoForm
    nav_section = "memories"
    url_basename = "memoryphoto"
    singular_name = "Memory Photo"


class MemoryPhotoDeleteView(DashboardDeleteView):
    model = MemoryPhoto
    nav_section = "memories"
    url_basename = "memoryphoto"
    singular_name = "Memory Photo"


class HomeVideoListView(DashboardListView):
    model = HomeVideo
    nav_section = "homevideo"
    url_basename = "homevideo"
    singular_name = "Home Video"
    plural_name = "Home Video"
    columns = [
        {"label": "Cover", "name": "poster", "type": "image"},
        {"label": "Title", "name": "title"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class HomeVideoCreateView(DashboardCreateView):
    model = HomeVideo
    form_class = forms.HomeVideoForm
    nav_section = "homevideo"
    url_basename = "homevideo"
    singular_name = "Home Video"


class HomeVideoUpdateView(DashboardUpdateView):
    model = HomeVideo
    form_class = forms.HomeVideoForm
    nav_section = "homevideo"
    url_basename = "homevideo"
    singular_name = "Home Video"


class HomeVideoDeleteView(DashboardDeleteView):
    model = HomeVideo
    nav_section = "homevideo"
    url_basename = "homevideo"
    singular_name = "Home Video"


class ServiceHighlightListView(DashboardListView):
    model = ServiceHighlight
    nav_section = "servicestrip"
    url_basename = "servicehighlight"
    singular_name = "Service Item"
    plural_name = "Service Strip"
    columns = [
        {"label": "Label", "name": "label"},
        {"label": "Icon", "name": "get_icon_display"},
        {"label": "Order", "name": "display_order"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class ServiceHighlightCreateView(DashboardCreateView):
    model = ServiceHighlight
    form_class = forms.ServiceHighlightForm
    nav_section = "servicestrip"
    url_basename = "servicehighlight"
    singular_name = "Service Item"


class ServiceHighlightUpdateView(DashboardUpdateView):
    model = ServiceHighlight
    form_class = forms.ServiceHighlightForm
    nav_section = "servicestrip"
    url_basename = "servicehighlight"
    singular_name = "Service Item"


class ServiceHighlightDeleteView(DashboardDeleteView):
    model = ServiceHighlight
    nav_section = "servicestrip"
    url_basename = "servicehighlight"
    singular_name = "Service Item"


class HeroSlideListView(DashboardListView):
    model = HeroSlide
    nav_section = "heroslides"
    url_basename = "heroslide"
    singular_name = "Hero Slide"
    plural_name = "Hero Slides"
    columns = [
        {"label": "Image", "name": "image", "type": "image"},
        {"label": "Title", "name": "title"},
        {"label": "Order", "name": "display_order"},
        {"label": "Active", "name": "is_active", "type": "bool"},
    ]


class HeroSlideCreateView(DashboardCreateView):
    model = HeroSlide
    form_class = forms.HeroSlideForm
    nav_section = "heroslides"
    url_basename = "heroslide"
    singular_name = "Hero Slide"


class HeroSlideUpdateView(DashboardUpdateView):
    model = HeroSlide
    form_class = forms.HeroSlideForm
    nav_section = "heroslides"
    url_basename = "heroslide"
    singular_name = "Hero Slide"


class HeroSlideDeleteView(DashboardDeleteView):
    model = HeroSlide
    nav_section = "heroslides"
    url_basename = "heroslide"
    singular_name = "Hero Slide"


class BlogPostListView(DashboardListView):
    model = BlogPost
    nav_section = "blog"
    url_basename = "blogpost"
    singular_name = "Blog Post"
    plural_name = "Blog Posts"
    search_fields = ["title", "slug"]
    columns = [
        {"label": "Title", "name": "title"},
        {"label": "Slug", "name": "slug"},
        {"label": "Published", "name": "is_published", "type": "bool"},
        {"label": "Publish at", "name": "publish_at", "type": "datetime"},
    ]


class BlogPostCreateView(DashboardCreateView):
    model = BlogPost
    form_class = forms.BlogPostForm
    nav_section = "blog"
    url_basename = "blogpost"
    singular_name = "Blog Post"


class BlogPostUpdateView(DashboardUpdateView):
    model = BlogPost
    form_class = forms.BlogPostForm
    nav_section = "blog"
    url_basename = "blogpost"
    singular_name = "Blog Post"


class BlogPostDeleteView(DashboardDeleteView):
    model = BlogPost
    nav_section = "blog"
    url_basename = "blogpost"
    singular_name = "Blog Post"


class PageListView(DashboardListView):
    model = Page
    nav_section = "pages"
    url_basename = "page"
    singular_name = "Page"
    plural_name = "Pages"
    search_fields = ["title", "slug"]
    columns = [
        {"label": "Title", "name": "title"},
        {"label": "Slug", "name": "slug"},
        {"label": "Published", "name": "is_published", "type": "bool"},
    ]


class PageCreateView(DashboardCreateView):
    model = Page
    form_class = forms.PageForm
    nav_section = "pages"
    url_basename = "page"
    singular_name = "Page"


class PageUpdateView(DashboardUpdateView):
    model = Page
    form_class = forms.PageForm
    nav_section = "pages"
    url_basename = "page"
    singular_name = "Page"


class PageDeleteView(DashboardDeleteView):
    model = Page
    nav_section = "pages"
    url_basename = "page"
    singular_name = "Page"


class FAQItemListView(DashboardListView):
    model = FAQItem
    nav_section = "faqs"
    url_basename = "faq"
    singular_name = "FAQ"
    plural_name = "FAQs"
    search_fields = ["question"]
    columns = [
        {"label": "Question", "name": "question"},
        {"label": "Order", "name": "display_order"},
        {"label": "Published", "name": "is_published", "type": "bool"},
    ]


class FAQItemCreateView(DashboardCreateView):
    model = FAQItem
    form_class = forms.FAQItemForm
    nav_section = "faqs"
    url_basename = "faq"
    singular_name = "FAQ"


class FAQItemUpdateView(DashboardUpdateView):
    model = FAQItem
    form_class = forms.FAQItemForm
    nav_section = "faqs"
    url_basename = "faq"
    singular_name = "FAQ"


class FAQItemDeleteView(DashboardDeleteView):
    model = FAQItem
    nav_section = "faqs"
    url_basename = "faq"
    singular_name = "FAQ"


class PolicyDocumentListView(DashboardListView):
    model = PolicyDocument
    nav_section = "pages"
    url_basename = "policy"
    singular_name = "Policy"
    plural_name = "Policy Documents"
    search_fields = ["title", "slug"]
    columns = [
        {"label": "Title", "name": "title"},
        {"label": "Type", "name": "policy_type"},
        {"label": "Published", "name": "is_published", "type": "bool"},
    ]


class PolicyDocumentCreateView(DashboardCreateView):
    model = PolicyDocument
    form_class = forms.PolicyDocumentForm
    nav_section = "pages"
    url_basename = "policy"
    singular_name = "Policy"


class PolicyDocumentUpdateView(DashboardUpdateView):
    model = PolicyDocument
    form_class = forms.PolicyDocumentForm
    nav_section = "pages"
    url_basename = "policy"
    singular_name = "Policy"


class PolicyDocumentDeleteView(DashboardDeleteView):
    model = PolicyDocument
    nav_section = "pages"
    url_basename = "policy"
    singular_name = "Policy"
