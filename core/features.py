"""Central feature switches, backed by the SiteSettings singleton."""

from __future__ import annotations

from functools import wraps

from django.http import Http404

from core.services import get_site_settings

FEATURE_FLAGS = {
    "delivery_integration": "delivery_integration_enabled",
    "brands": "brands_enabled",
    "subscriptions": "subscriptions_enabled",
    "rentals": "rentals_enabled",
    "gift_builder": "gift_builder_enabled",
    "newsletter": "newsletter_enabled",
}


def is_enabled(feature: str) -> bool:
    """Return whether a feature switch (key of FEATURE_FLAGS) is currently ON."""
    return bool(getattr(get_site_settings(), FEATURE_FLAGS[feature]))


class FeatureGatedAdminMixin:
    """ModelAdmin mixin: while ``feature_key`` is OFF, hide the model and deny all access to it."""

    feature_key: str

    def _feature_on(self) -> bool:
        return is_enabled(self.feature_key)

    def has_module_permission(self, request) -> bool:
        return self._feature_on() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None) -> bool:
        return self._feature_on() and super().has_view_permission(request, obj)

    def has_add_permission(self, request) -> bool:
        return self._feature_on() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None) -> bool:
        return self._feature_on() and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None) -> bool:
        return self._feature_on() and super().has_delete_permission(request, obj)


def feature_required(feature: str):
    """View decorator: respond 404 while the feature is switched OFF."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_enabled(feature):
                raise Http404
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
