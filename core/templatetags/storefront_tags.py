"""Storefront template helpers for currency display."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()


def _format_money_amount(value: Decimal) -> str:
    """Format money without trailing .00; keep decimals only when needed."""
    quantized = value.quantize(Decimal("0.01"), ROUND_HALF_UP)
    if quantized == quantized.to_integral_value():
        return f"{int(quantized)}"
    text = f"{quantized:.2f}".rstrip("0").rstrip(".")
    return text


@register.filter
def in_display_currency(amount, currency) -> str:
    """Convert a base-currency amount into the active display currency."""
    if amount is None or amount == "":
        return ""
    if currency is None:
        try:
            return _format_money_amount(Decimal(str(amount)))
        except Exception:
            return str(amount)
    base = Decimal(str(amount))
    rate = Decimal(str(currency.exchange_rate_to_base))
    if rate <= 0:
        return _format_money_amount(base)
    converted = (base / rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return _format_money_amount(converted)


@register.simple_tag
def money_label(amount, currency) -> str:
    """Format amount with currency symbol for templates."""
    symbol = getattr(currency, "symbol", "")
    value = in_display_currency(amount, currency)
    return f"{symbol} {value}".strip()


@register.filter
def splitlines(value) -> list[str]:
    """Split text into non-blank, stripped lines (e.g. announcement messages)."""
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


@register.filter
def line_icon(line: str) -> str:
    """Icon name prefix of a ``"icon: text"`` line, or an empty string."""
    from core.icons import split_icon

    return split_icon(str(line))[0]


@register.filter
def line_text(line: str) -> str:
    """Text of a ``"icon: text"`` line with the icon prefix removed."""
    from core.icons import split_icon

    return split_icon(str(line))[1]


_SWATCH_KEYWORDS = (
    ("black", "#1a1a1a"),
    ("white", "#ffffff"),
    ("ivory", "#f8f1e7"),
    ("cream", "#f3e8dc"),
    ("beige", "#d8c3a5"),
    ("tan", "#d2b48c"),
    ("brown", "#6b4226"),
    ("maroon", "#4a0908"),
    ("red", "#b3202c"),
    ("pink", "#e8a0b4"),
    ("rose", "#c97b8a"),
    ("orange", "#d96c2b"),
    ("mustard", "#c9971f"),
    ("yellow", "#d9a441"),
    ("gold", "#b8893b"),
    ("green", "#3f6b4a"),
    ("olive", "#6b6b3a"),
    ("teal", "#2f6f6a"),
    ("navy", "#1c2b4a"),
    ("blue", "#2a4d78"),
    ("purple", "#5c3a6b"),
    ("lavender", "#9b8bb4"),
    ("grey", "#8a8a86"),
    ("gray", "#8a8a86"),
    ("silver", "#c0c0c0"),
)


@register.filter
def swatch_color(value) -> str:
    """
    Best-effort hex color for a free-text color name, for a decorative swatch
    dot only — the real color name is always shown as text alongside it, so
    an inexact match here (e.g. an unrecognized/compound name) is harmless.
    """
    if not value:
        return "transparent"
    lowered = str(value).lower()
    for keyword, hex_code in _SWATCH_KEYWORDS:
        if keyword in lowered:
            return hex_code
    return "#cbbfae"
