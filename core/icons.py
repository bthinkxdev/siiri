"""Names of the built-in storefront line icons (see templates/includes/_icon.html)."""

from __future__ import annotations

ICON_NAMES = (
    "truck",
    "shield",
    "globe",
    "star",
    "headset",
    "return",
    "card",
    "gift",
    "heart",
    "leaf",
    "weave",
)
ICON_CHOICES = [(name, name.title()) for name in ICON_NAMES]


def split_icon(line: str) -> tuple[str, str]:
    """Split ``"truck: Free shipping"`` into ``("truck", "Free shipping")``; no known prefix gives ``("", line)``."""
    head, sep, rest = line.partition(":")
    name = head.strip().lower()
    if sep and name in ICON_NAMES and rest.strip():
        return name, rest.strip()
    return "", line.strip()
