"""ModelForms used by the admin dashboard CRUD screens."""

from __future__ import annotations

import datetime

from django import forms

from dashboard.pending_uploads import PendingUploadMixin
from django.utils.text import slugify

from accounts.models import CustomerProfile
from catalog.models import (
    Brand,
    Collection,
    Fabric,
    Grade,
    Occasion,
    Product,
    ProductImage,
    ProductSpecification,
    ProductVariant,
    Review,
    SizeChart,
    Style,
)
from cms.models import BlogPost, FAQItem, HeroSlide, HomepageSection, Page, PolicyDocument, PromoBanner, ServiceHighlight, Testimonial, HomeVideo, MemoryPhoto
from core.models import SiteSettings, Currency

from marketing.models import Coupon, FlashSale, NewsletterSubscriber

_DATE = forms.DateInput(attrs={"type": "date"})
_DATETIME = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
_TIME = forms.TimeInput(attrs={"type": "time"})


class SlugAutoMixin(forms.ModelForm):
    """Auto-populate an empty ``slug`` from ``name``/``title`` on save."""

    def clean(self):
        cleaned = super().clean()
        if "slug" in self.fields and not cleaned.get("slug"):
            source = cleaned.get("name") or cleaned.get("title")
            if source:
                cleaned["slug"] = slugify(source)
        return cleaned


class ProductForm(PendingUploadMixin, SlugAutoMixin):
    pending_upload_fields = ("og_image",)

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "sku",
            "hsn_code",
            "collections",
            "styles",
            "fabrics",
            "occasions",
            "grades",
            "brand",
            "size_chart",
            "base_price",
            "mrp",
            "purchase_price",

            "color",
            "stock_quantity",
            "low_stock_threshold",
            "is_active",
            "is_featured",
            "is_bestseller",
            "is_new_arrival",
            "show_home_spotlight",
            "description",
            "care_instructions",
            "meta_title",
            "meta_description",
            "og_image",
            "weight",
            "length",
            "width",
            "height",
        ]
        widgets = {
            "collections": forms.CheckboxSelectMultiple,
            "styles": forms.CheckboxSelectMultiple,
            "fabrics": forms.CheckboxSelectMultiple,
            "occasions": forms.CheckboxSelectMultiple,
            "grades": forms.CheckboxSelectMultiple,
        }
        error_messages = {
            "name": {"required": "Product name is required."},
            "sku": {"required": "SKU is required."},
            "base_price": {"required": "Base price is required."},
            "mrp": {"required": "MRP is required."},
            "purchase_price": {"required": "Purchase price is required."},
            "stock_quantity": {"required": "Stock quantity is required."},
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.features import is_enabled
        if not is_enabled("brands"):
            #field is hidden while Brands is OFF; dropping it keeps an existing brand intact on save
            self.fields.pop("brand", None)
        from django.db.models import Q
        for field_name in ("collections", "styles", "fabrics", "occasions", "grades"):
            field = self.fields[field_name]
            field.required = False
           
            active_q = Q(is_active=True)
            if self.instance and self.instance.pk:
                linked_ids = list(getattr(self.instance, field_name).values_list("pk", flat=True))
                if linked_ids:
                    active_q |= Q(pk__in=linked_ids)
            field.queryset = field.queryset.filter(active_q)
            field.label_from_instance = (
                lambda obj: obj.name if obj.is_active else f"{obj.name} (inactive)"
            )
        for field_name in ("description", "care_instructions"):
            self.fields[field_name].widget.attrs["class"] = "tinymce-editor"
            self.fields[field_name].widget.attrs["style"] = "visibility: hidden; height: 260px;"
        from django.db.models import Q
        qs = SizeChart.objects.filter(is_active=True)
        if self.instance and self.instance.pk and self.instance.size_chart_id:
            qs = SizeChart.objects.filter(Q(is_active=True) | Q(pk=self.instance.size_chart_id))
        self.fields["size_chart"].queryset = qs.order_by("name")
        self.fields["size_chart"].empty_label = "No Size Chart"
        self.fields["slug"].required = False
        self.fields["hsn_code"].required = False
        self.fields["base_price"].required = False
        self.fields["mrp"].required = False
        self.fields["purchase_price"].required = False
        self.fields["stock_quantity"].required = False
        self.fields["low_stock_threshold"].required = False

        for name, label in (
            ("base_price", "Base price"),
            ("mrp", "MRP"),
            ("purchase_price", "Purchase price"),
            ("stock_quantity", "Stock quantity"),
        ):
            self.fields[name].widget.attrs["data-required-msg"] = (
                f"{label} is required when the product has no variants."
            )

    def clean(self):
        cleaned = super().clean()
        for field in ["base_price", "mrp", "purchase_price", "stock_quantity", "low_stock_threshold"]:
            if cleaned.get(field) is None:
                cleaned[field] = 0
        return cleaned


class CollectionForm(SlugAutoMixin):
    class Meta:
        model = Collection
        fields = [
            "name",
            "slug",
            "display_order",
            "is_active",
            "show_on_homepage",
            "tagline",
            "meta_title",
            "meta_description",
            "og_image",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class _FacetForm(SlugAutoMixin):
    """Shared form shape for the flat Style/Fabric/Occasion/Grade facets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class StyleForm(_FacetForm):
    class Meta:
        model = Style
        fields = ["name", "slug", "display_order", "is_active"]


class FabricForm(_FacetForm):
    class Meta:
        model = Fabric
        fields = ["name", "slug", "display_order", "is_active"]


class OccasionForm(_FacetForm):
    class Meta:
        model = Occasion
        fields = ["name", "slug", "display_order", "is_active"]


class GradeForm(_FacetForm):
    class Meta:
        model = Grade
        fields = ["name", "slug", "display_order", "is_active"]



class BrandForm(SlugAutoMixin):
    class Meta:
        model = Brand
        fields = ["name", "slug", "logo", "is_featured"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class SizeChartForm(forms.ModelForm):
    class Meta:
        model = SizeChart
        fields = ["name", "content_html", "image", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content_html"].widget.attrs["class"] = "tinymce-editor"
        self.fields["content_html"].widget.attrs["style"] = "visibility: hidden; height: 300px;"


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["moderation_status"]


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ["variant_type", "name", "base_price", "mrp", "purchase_price", "sku_suffix", "stock_quantity", "low_stock_threshold", "is_default"]
        widgets = {
            "variant_type": forms.TextInput(attrs={
                "list": "variant-type-list",
                "class": "form-control",
                "placeholder": "e.g. Size, Packaging, Color"
            }),
        }
        error_messages = {
            "variant_type": {"required": "Variant type is required."},
            "name": {"required": "Name is required."},
            "base_price": {"required": "Base price is required."},
            "mrp": {"required": "MRP is required."},
            "purchase_price": {"required": "Purchase price is required."},
            "stock_quantity": {"required": "Stock quantity is required."},
            "low_stock_threshold": {"required": "Low stock threshold is required."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for name, field in self.fields.items():
            if field.required and name in self.Meta.error_messages:
                field.widget.attrs["data-required-msg"] = self.Meta.error_messages[name]["required"]
        if not self.instance.pk:
            
            for name in ("base_price", "mrp", "purchase_price"):
                self.initial[name] = None

    def has_changed(self):
        """
        A row counts as "touched" if any field was submitted with a non-blank
        value — deliberately not deferring to the default has_changed(), which
        compares against the new instance's own field defaults (stock_quantity
        0, low_stock_threshold 5) and so would call an explicitly-filled-in row
        matching those defaults "unchanged", silently dropping it.
        """
        for name in self.fields:
            prefixed_name = self.add_prefix(name)
            val = self.data.get(prefixed_name)
            if val not in (None, ""):
                return True
        return False

class ProductVariantInlineFormSet(forms.BaseInlineFormSet):
    """
    Cross-row validation that a single form can't do on its own: dedupe
    variant_type casing within a product, reject SKU-suffix collisions, and
    enforce at most one default variant. Deliberately application-level only
    (no DB constraint/migration) so it can't fail against any duplicate/blank
    data already sitting in production.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        #a product being created is unsaved and has no existing variants to
        #collide with; filtering by it would raise ValueError.
        existing_variants = (
            ProductVariant.objects.filter(product=self.instance)
            if self.instance.pk
            else ProductVariant.objects.none()
        )
        seen_types: dict[str, str] = {}
        seen_skus: dict[str, int] = {}
        default_count = 0

        for form in self.forms:
            if not getattr(form, "cleaned_data", None) or form.cleaned_data.get("DELETE"):
                continue

            variant_type = (form.cleaned_data.get("variant_type") or "").strip()
            if variant_type:
                key = variant_type.lower()
                canonical = seen_types.get(key)
                if canonical is None:
                    existing = existing_variants.filter(
                        variant_type__iexact=variant_type
                    ).exclude(pk=form.instance.pk).first()
                    canonical = existing.variant_type if existing else variant_type
                    seen_types[key] = canonical
                form.cleaned_data["variant_type"] = canonical
                form.instance.variant_type = canonical

            sku_suffix = (form.cleaned_data.get("sku_suffix") or "").strip()
            if sku_suffix:
                key = sku_suffix.lower()
                if key in seen_skus:
                    form.add_error("sku_suffix", "This SKU suffix is used by another variant in this submission.")
                else:
                    seen_skus[key] = 1
                    conflict = existing_variants.filter(
                        sku_suffix__iexact=sku_suffix
                    ).exclude(pk=form.instance.pk).first()
                    if conflict:
                        form.add_error("sku_suffix", f'SKU suffix "{sku_suffix}" is already used by another variant of this product.')

            if form.cleaned_data.get("is_default"):
                default_count += 1
                if default_count > 1:
                    form.add_error("is_default", "Only one variant can be marked as default.")

ProductVariantFormSet = forms.inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    formset=ProductVariantInlineFormSet,
    extra=0,
    can_delete=True,
)

class ProductImageForm(PendingUploadMixin, forms.ModelForm):
    pending_upload_fields = ("image",)

    class Meta:
        model = ProductImage
        fields = ["image", "alt_text", "display_order", "is_primary"]
        error_messages = {
            "image": {"required": "Image file is required."},
            "alt_text": {"required": "Alt text is required."},
            "display_order": {"required": "Display order is required."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].widget.attrs["class"] = "form-control form-control-sm"

ProductImageFormSet = forms.inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    extra=1,
    can_delete=True,
)
class ProductSpecificationForm(forms.ModelForm):
    class Meta:
        model = ProductSpecification
        fields = ["name", "value", "display_order"]
        error_messages = {
            "name": {"required": "Specification name is required."},
            "value": {"required": "Value is required."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_order"].required = False
        if not self.instance.pk:
            self.initial["display_order"] = None

    def clean_display_order(self):
        val = self.cleaned_data.get("display_order")
        return val if val is not None else 0


ProductSpecificationFormSet = forms.inlineformset_factory(
    Product,
    ProductSpecification,
    form=ProductSpecificationForm,
    extra=1,
    can_delete=True,
)


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = [
            "phone",
            "phone_verified",
            "notify_via_email",
            "notify_via_sms",
            "notify_via_whatsapp",
        ]




class NoPastDatesMixin:
    """Restricts datetime fields to today or later (Asia/Kolkata local day).

    """

    no_past_date_fields: tuple = ()
    date_range_fields: tuple = ()
    _MIN_FORMAT = "%Y-%m-%dT%H:%M"

    @staticmethod
    def _today_start():
        from django.utils import timezone

        return timezone.make_aware(
            datetime.datetime.combine(timezone.localdate(), datetime.time.min)
        )

    def _original_value(self, name):
        if self.instance and self.instance.pk:
            return getattr(self.instance, name, None)
        return None

    def _setup_no_past_dates(self):
        from django.utils import timezone

        today_start = self._today_start()
        for name in self.no_past_date_fields:
            field = self.fields.get(name)
            if not field:
                continue
            floor = today_start
            original = self._original_value(name)
            if original and original < today_start:
                floor = original
            field.widget.attrs["min"] = timezone.localtime(floor).strftime(self._MIN_FORMAT)
        if len(self.date_range_fields) == 2:
            start, end = self.date_range_fields
            if start in self.fields and end in self.fields:
                # dashboard.js keeps the end picker's min in step with the start value.
                self.fields[end].widget.attrs["data-min-from"] = self[start].auto_id

    def _clean_no_past_dates(self, cleaned_data):
        today_start = self._today_start()
        for name in self.no_past_date_fields:
            value = cleaned_data.get(name)
            if not value or value >= today_start:
                continue
            original = self._original_value(name)
            unchanged = original is not None and original.replace(second=0, microsecond=0) == value.replace(
                second=0, microsecond=0
            )
            if not unchanged:
                self.add_error(name, "Past dates are not allowed. Please choose today or a future date.")
        if len(self.date_range_fields) == 2:
            start_name, end_name = self.date_range_fields
            start, end = cleaned_data.get(start_name), cleaned_data.get(end_name)
            if start and end and end <= start and end_name not in self.errors:
                self.add_error(end_name, "End date must be after the start date.")
        return cleaned_data


class CouponForm(NoPastDatesMixin, forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code",
            "discount_type",
            "discount_value",
            "min_order_value",
            "max_uses",
            "max_uses_per_customer",
            "valid_from",
            "valid_until",
            "applicable_collections",
            "is_active",
        ]
        widgets = {"valid_from": _DATETIME, "valid_until": _DATETIME}

    no_past_date_fields = ("valid_from", "valid_until")
    date_range_fields = ("valid_from", "valid_until")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_no_past_dates()
        if self.instance and self.instance.pk:
            from django.utils import timezone
            now = timezone.now()
            if self.instance.valid_until and self.instance.valid_until < now:
                self.initial["is_active"] = False

    def clean(self):
        cleaned_data = self._clean_no_past_dates(super().clean())
        valid_until = cleaned_data.get("valid_until")
        is_active = cleaned_data.get("is_active")
        
        from django.utils import timezone
        now = timezone.now()
        
        if valid_until and valid_until < now and is_active:
            cleaned_data["is_active"] = False
            
        return cleaned_data



class FlashSaleForm(NoPastDatesMixin, forms.ModelForm):
    class Meta:
        model = FlashSale
        fields = ["name", "products", "discount_percentage", "starts_at", "ends_at", "is_active"]
        widgets = {"starts_at": _DATETIME, "ends_at": _DATETIME}

    no_past_date_fields = ("starts_at", "ends_at")
    date_range_fields = ("starts_at", "ends_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_no_past_dates()
        if self.instance and self.instance.pk:
            from django.utils import timezone
            now = timezone.now()
            if self.instance.ends_at and self.instance.ends_at < now:
                self.initial["is_active"] = False

    def clean(self):
        cleaned_data = self._clean_no_past_dates(super().clean())
        ends_at = cleaned_data.get("ends_at")
        is_active = cleaned_data.get("is_active")
        
        from django.utils import timezone
        now = timezone.now()
        
        if ends_at and ends_at < now and is_active:
            cleaned_data["is_active"] = False
            
        return cleaned_data


class NewsletterSubscriberForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ["email", "is_active"]


class HomepageSectionForm(forms.ModelForm):
    """Section order is set by drag and drop on the list page, so it is not an editable field here."""

    class Meta:
        model = HomepageSection
        fields = ["section_type", "title", "is_active", "config"]

    def clean(self):
        cleaned = super().clean()
        from cms.models import HomepageSectionType

        if cleaned.get("section_type") == HomepageSectionType.INSTAGRAM_GALLERY and cleaned.get("is_active"):
            from cms.section_context import resolve_instagram_section

            config = cleaned.get("config") if isinstance(cleaned.get("config"), dict) else {}
            resolved = resolve_instagram_section(config)
            if not resolved["instagram_handle"] and not resolved["posts"]:
                self.add_error(
                    "config",
                    'The Instagram Gallery has nothing to show yet, so it would not appear on the home page. '
                    'Add your handle here, e.g. {"instagram_handle": "siricouture"} '
                    '(optionally with "post_urls": ["https://.../photo1.jpg", ...]), '
                    "or set the Instagram URL in Site Settings.",
                )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk is None:
            from django.db.models import Max

            last = HomepageSection.objects.aggregate(last=Max("display_order"))["last"]
            instance.display_order = 0 if last is None else last + 1
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class PromoBannerForm(forms.ModelForm):
    class Meta:
        model = PromoBanner
        fields = [
            "style",
            "eyebrow",
            "title",
            "subtitle",
            "cta_label",
            "cta_url",
            "image",
            "display_order",
            "is_active",
        ]

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image:
            from django.core.files.images import get_image_dimensions

            width, _height = get_image_dimensions(image)
            if width and width < 600:
                raise forms.ValidationError(
                    f"Promo image must be at least 600px wide for good quality. Uploaded image is {width}px wide."
                )
        return image


class TestimonialForm(forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ["name", "location", "quote", "photo", "rating", "display_order", "is_active"]
        widgets = {"quote": forms.Textarea(attrs={"rows": 4})}


class MemoryPhotoForm(forms.ModelForm):
    class Meta:
        model = MemoryPhoto
        fields = ["image", "caption", "display_order", "is_active"]

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, "content_type"):
            from django.core.files.images import get_image_dimensions

            width, _height = get_image_dimensions(image)
            if width and width < 600:
                raise forms.ValidationError(
                    f"Photo must be at least 600px wide for good quality. Uploaded photo is {width}px wide."
                )
        return image


class HomeVideoForm(forms.ModelForm):
    class Meta:
        model = HomeVideo
        fields = ["title", "subtitle", "video", "poster", "display_order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_order"].required = False

    def clean_display_order(self):
        value = self.cleaned_data.get("display_order")
        return 0 if value is None else value


class ServiceHighlightForm(forms.ModelForm):
    class Meta:
        model = ServiceHighlight
        fields = ["icon", "label", "display_order", "is_active"]


class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = [
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
        ]

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image:
            from django.core.files.images import get_image_dimensions
            width, height = get_image_dimensions(image)
            
            # Landscape banner around the 2.56:1 design ratio; older 2:1 uploads stay valid.
            aspect_ratio = width / height
            if not (1.95 <= aspect_ratio <= 2.85):
                raise forms.ValidationError(
                    f"Banner image must be landscape, between 2:1 and 2.8:1 (recommended 2400x940). "
                    f"Uploaded image is {width}x{height}."
                )

            # Minimum resolution for quality
            if width < 1000:
                raise forms.ValidationError(
                    f"Banner image must be at least 1000px wide for good quality. Uploaded image is {width}px wide."
                )

        return image

    def clean_poster(self):
        poster = self.cleaned_data.get("poster")
        if poster:
            from django.core.files.images import get_image_dimensions

            width, height = get_image_dimensions(poster)
            # same landscape range as the banner photo so a video poster matches its slide
            if not (1.95 <= width / height <= 2.85):
                raise forms.ValidationError(
                    f"Poster image must be a wide landscape image (about 2:1 to 2.8:1). "
                    f"Uploaded image is {width}x{height}."
                )

            if width < 1000:
                raise forms.ValidationError(
                    f"Poster image must be at least 1000px wide. Uploaded image is {width}px wide."
                )

        return poster


class BlogPostForm(SlugAutoMixin):
    class Meta:
        model = BlogPost
        fields = [
            "title",
            "slug",
            "excerpt",
            "body",
            "is_published",
            "publish_at",
            "meta_title",
            "meta_description",
            "og_image",
        ]
        widgets = {"publish_at": _DATETIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class PageForm(SlugAutoMixin):
    class Meta:
        model = Page
        fields = [
            "title",
            "slug",
            "body",
            "is_published",
            "publish_at",
            "meta_title",
            "meta_description",
            "og_image",
        ]
        widgets = {"publish_at": _DATETIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class FAQItemForm(forms.ModelForm):
    class Meta:
        model = FAQItem
        fields = ["question", "answer", "display_order", "is_published", "publish_at"]
        widgets = {"publish_at": _DATETIME}


class PolicyDocumentForm(SlugAutoMixin):
    class Meta:
        model = PolicyDocument
        fields = [
            "title",
            "slug",
            "policy_type",
            "body",
            "is_published",
            "publish_at",
            "meta_title",
            "meta_description",
            "og_image",
        ]
        widgets = {"publish_at": _DATETIME}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False








class SiteSettingsForm(forms.ModelForm):
    default_currency = forms.ModelChoiceField(
        queryset=Currency.objects.all(),
        required=False,
        empty_label="--- Select Default Currency ---",
        help_text="Select the store's default currency."
    )

    field_order = [
        "site_name",
        "logo",
        "site_tagline",
        "announcement_messages",
        "primary_color",
        "secondary_color",
        "font_family",
        "facebook_url",
        "instagram_url",
        "twitter_url",
        "whatsapp_number",
        "store_address",
        "vendor_email",
        "order_notification_email",
        "tax_rate_percent",
        "cod_delivery_charge",
        "default_currency",
        "razorpay_key_id",
        "razorpay_key_secret",
        "featured_label",
        "bestseller_label",
        "new_arrival_label",
        "delivery_integration_enabled",
        "brands_enabled",
        "subscriptions_enabled",
        "rentals_enabled",
        "gift_builder_enabled",
        "newsletter_enabled",
    ]

    class Meta:
        model = SiteSettings
        fields = [
            "site_name",
            "logo",
            "site_tagline",
            "announcement_messages",
            "primary_color",
            "secondary_color",
            "font_family",
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "whatsapp_number",
            "store_address",
            "vendor_email",
            "order_notification_email",
            "tax_rate_percent",
            "cod_delivery_charge",
            "razorpay_key_id",
            "razorpay_key_secret",
            "featured_label",
            "bestseller_label",
            "new_arrival_label",
            "delivery_integration_enabled",
            "brands_enabled",
            "subscriptions_enabled",
            "rentals_enabled",
            "gift_builder_enabled",
            "newsletter_enabled",
        ]
        labels = {
            "vendor_email": "Email",
            "order_notification_email": "New Order Notification Email",
        }
        widgets = {
            "announcement_messages": forms.Textarea(attrs={"rows": 3}),
            "store_address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        default_curr = Currency.objects.filter(is_default=True).first()
        if default_curr:
            self.fields["default_currency"].initial = default_curr.pk
        for field_name, field in self.fields.items():
            if field_name != "logo" and not isinstance(field.widget, forms.CheckboxInput):
                if "class" in field.widget.attrs:
                    field.widget.attrs["class"] += " form-control"
                else:
                    field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        instance = super().save(commit)
        new_default = self.cleaned_data.get("default_currency")
        if new_default:
            Currency.objects.update(is_default=False)
            new_default.is_default = True
            new_default.save()
            from core.selectors import invalidate_default_currency_cache
            invalidate_default_currency_cache()
        return instance


class OrderStatusForm(forms.Form):
    """Free-standing form for applying an order status transition."""

    new_status = forms.ChoiceField(choices=[])
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, allowed_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_status"].choices = allowed_choices or []
