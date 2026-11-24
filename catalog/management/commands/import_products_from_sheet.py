"""Bulk-create products from the client's Excel sheet, attaching images by SKU.

Image lookup per product (HEIC files are converted to JPEG):
  1. an image named after the product's own SKU,
  2. else the parent image (same 8-digit base SKU, no ``-N`` suffix),
  3. else the product is created without an image.

Existing SKUs are never touched, so the command is safe to re-run.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.models import (
    Brand,
    Collection,
    Fabric,
    Grade,
    Occasion,
    Product,
    ProductImage,
    Style,
)

TEMPLATE_SAMPLE_SKU = "SIIRI-SAREE-001"
IMAGE_EXTENSIONS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_EDGE = 2000
JPEG_QUALITY = 90

_FILENAME_SKU = re.compile(r"^(\d{8})(?:-(\d+))?(?=[\s-])")
_SKU = re.compile(r"^(\d{8})(?:-(\d+))?$")

# Sheet column (header minus the trailing " *") -> facet model, for the M2M columns.
FACETS = {
    "Collections": ("collections", Collection),
    "Styles": ("styles", Style),
    "Fabrics": ("fabrics", Fabric),
    "Occasions": ("occasions", Occasion),
    "Grades": ("grades", Grade),
}
REQUIRED_HEADERS = {"SKU", "Product Name", "MRP", "Selling Price", "Stock Quantity"}


@dataclass
class Row:
    line: int
    sku: str
    name: str
    description: str
    care: str
    brand: str
    color: str
    hsn: str
    mrp: Decimal
    price: Decimal
    purchase: Decimal | None
    stock: int
    facets: dict[str, list[str]]
    warnings: list[str] = field(default_factory=list)


def _clean(value) -> str:
    return re.sub(r"[ \t]+", " ", str(value)).strip() if value is not None else ""


def _sku(value) -> str:
    """Excel stores numeric SKUs as floats (41596819.0) — normalise to a plain string."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _clean(value)


def _name(value) -> str:
    """Tidy spacing/hyphens/casing: 'Tussar saree- pink ' -> 'Tussar Saree - Pink'."""
    return re.sub(r"\s*-\s*", " - ", _clean(value)).title()


def _money(value, line: int, column: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise CommandError(f"Row {line}: {column} is not a number: {value!r}")


def _sku_key(base: str, suffix: str | None) -> str:
    """Canonical SKU key so '70773451-03' (file) matches '70773451-03' / '-3' (sheet)."""
    return f"{base}-{int(suffix)}" if suffix else base


def _facet_values(value) -> list[str]:
    names = [n[:1].upper() + n[1:] for n in (_clean(p) for p in str(value or "").split(",")) if n]
    return names


class Command(BaseCommand):
    help = "Create products from the client Excel sheet and attach images by SKU (idempotent)."

    def add_arguments(self, parser) -> None:
        folder = Path(settings.BASE_DIR) / "newProductImage"
        parser.add_argument("--sheet", default=str(folder / "SIIRI_PRODUCT_SHEET.xlsx"))
        parser.add_argument("--images-dir", default=str(folder))
        parser.add_argument("--dry-run", action="store_true", help="Report the plan without writing anything.")

    def handle(self, *args, **options) -> None:
        dry_run = options["dry_run"]
        rows = self._read_sheet(Path(options["sheet"]))
        images = self._index_images(Path(options["images_dir"]))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be written."))

        name_counts: dict[str, int] = {}
        for row in rows:
            name_counts[row.name.lower()] = name_counts.get(row.name.lower(), 0) + 1

        self._heif_ready = False
        self._jpeg_cache: dict[Path, bytes] = {}
        used_files: set[Path] = set()
        stats = {"created": 0, "skipped": 0, "own": 0, "parent": 0, "none": 0}
        no_image: list[str] = []

        for row in rows:
            if Product.objects.filter(sku__iexact=row.sku).exists():
                stats["skipped"] += 1
                self.stdout.write(f"SKIP   {row.sku} — already exists")
                continue

            path, source = self._find_image(row.sku, images)
            stats[source] += 1
            if path:
                used_files.add(path)
            else:
                no_image.append(row.sku)
            for warning in row.warnings:
                self.stdout.write(self.style.WARNING(f"  row {row.line} ({row.sku}): {warning}"))
            label = {"own": path.name if path else "", "parent": f"PARENT image {path.name}" if path else "", "none": "NO IMAGE"}[source]
            self.stdout.write(f"CREATE {row.sku:<12} {row.name} -> {label}")

            if dry_run:
                stats["created"] += 1
                continue
            with transaction.atomic():
                self._create_product(row, path, unique_name=name_counts[row.name.lower()] == 1)
            stats["created"] += 1

        if any(r.purchase is None for r in rows):
            self.stdout.write(self.style.WARNING("Purchase Price is blank in the sheet for some rows; those are stored as 0."))
        unused = sorted(p.name for ps in images.values() for p in ps if p not in used_files)
        verb = "would be created" if dry_run else "created"
        self.stdout.write(self.style.SUCCESS(
            f"\n{stats['created']} product(s) {verb}, {stats['skipped']} skipped (already exist). "
            f"Images: {stats['own']} own, {stats['parent']} from parent, {stats['none']} without."
        ))
        if no_image:
            self.stdout.write(self.style.WARNING("Created without image: " + ", ".join(no_image)))
        if unused:
            self.stdout.write(self.style.WARNING("Image files not used by any new product: " + "; ".join(unused)))

    # ---------------------------------------------------------------- reading

    def _read_sheet(self, path: Path) -> list[Row]:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise CommandError("openpyxl is required: pip install -r requirements.txt") from exc
        if not path.is_file():
            raise CommandError(f"Sheet not found: {path}")

        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            return self._parse_rows(list(workbook["Products"].iter_rows(values_only=True)))
        finally:
            workbook.close()

    def _parse_rows(self, sheet_rows: list[tuple]) -> list[Row]:
        lines = iter(sheet_rows)
        headers = [re.sub(r"\s*\*$", "", _clean(h)) for h in next(lines)]
        missing = REQUIRED_HEADERS - set(headers)
        if missing:
            raise CommandError(f"Sheet is missing column(s): {', '.join(sorted(missing))}")
        col = {h: i for i, h in enumerate(headers) if h}

        rows: list[Row] = []
        seen: dict[str, int] = {}
        for line, cells in enumerate(lines, start=2):
            get = lambda h: cells[col[h]] if h in col and col[h] < len(cells) else None  # noqa: E731
            sku, name = _sku(get("SKU")), _name(get("Product Name"))
            if not sku and not name:
                continue  # leftover filler row
            if sku == TEMPLATE_SAMPLE_SKU:
                continue
            if not sku or not name:
                raise CommandError(f"Row {line}: SKU and Product Name are both required.")
            if not _SKU.match(sku):
                raise CommandError(f"Row {line}: unexpected SKU format {sku!r} (want 12345678 or 12345678-1).")
            if sku.lower() in seen:
                raise CommandError(f"Row {line}: SKU {sku} duplicates row {seen[sku.lower()]}.")
            seen[sku.lower()] = line

            mrp, price = _money(get("MRP"), line, "MRP"), _money(get("Selling Price"), line, "Selling Price")
            if mrp is None or price is None:
                raise CommandError(f"Row {line} ({sku}): MRP and Selling Price are required.")
            warnings: list[str] = []
            if price > mrp:
                warnings.append(f"selling price {price} is above MRP {mrp}; MRP raised to {price} — please confirm with client")
                mrp = price
            purchase = _money(get("Purchase Price"), line, "Purchase Price")

            rows.append(Row(
                line=line, sku=sku, name=name,
                description=str(get("Description") or "").strip(),
                care=_clean(get("Care Instructions")),
                brand=_clean(get("Brand")), color=_clean(get("Color")), hsn=_clean(get("HSN Code")),
                mrp=mrp, price=price, purchase=purchase,
                stock=int(get("Stock Quantity") or 0),
                facets={h: _facet_values(get(h)) for h in FACETS},
                warnings=warnings,
            ))
        if not rows:
            raise CommandError("No product rows found in the sheet.")
        return rows

    def _index_images(self, folder: Path) -> dict[str, list[Path]]:
        if not folder.is_dir():
            raise CommandError(f"Images folder not found: {folder}")
        index: dict[str, list[Path]] = {}
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            m = _FILENAME_SKU.match(f.name)
            if m:
                index.setdefault(_sku_key(*m.groups()), []).append(f)
        return index

    @staticmethod
    def _find_image(sku: str, images: dict[str, list[Path]]) -> tuple[Path | None, str]:
        base, suffix = _SKU.match(sku).groups()
        key = _sku_key(base, suffix)
        if images.get(key):
            return images[key][0], "own"
        if suffix and images.get(base):  # parent = the un-suffixed base SKU
            return images[base][0], "parent"
        return None, "none"

    # ---------------------------------------------------------------- writing

    def _create_product(self, row: Row, image: Path | None, *, unique_name: bool) -> None:
        brand = self._get_or_create(Brand, row.brand) if row.brand else None
        product = Product.objects.create(
            name=row.name,
            slug=self._unique_slug(Product, row.name if unique_name else f"{row.name} {row.sku}", fallback=row.sku),
            sku=row.sku,
            hsn_code=row.hsn or None,
            brand=brand,
            base_price=row.price,
            mrp=row.mrp,
            purchase_price=row.purchase if row.purchase is not None else Decimal("0"),
            color=row.color,
            description=row.description,
            care_instructions=row.care,
            stock_quantity=row.stock,
        )
        for header, (attr, model) in FACETS.items():
            objs = [self._get_or_create(model, n) for n in row.facets[header]]
            if objs:
                getattr(product, attr).add(*objs)
        if image:
            ProductImage.objects.create(
                product=product,
                image=ContentFile(self._to_jpeg(image), name=f"{row.sku}.jpg"),
                alt_text=row.name,
                display_order=0,
                is_primary=True,
            )

    def _get_or_create(self, model, name: str):
        """Case-insensitive match on name so 'linen ' / 'Linen' / 'linen' share one record."""
        obj = model.objects.filter(name__iexact=name).first()
        if obj:
            return obj
        return model.objects.create(name=name, slug=self._unique_slug(model, name, fallback="item"))

    @staticmethod
    def _unique_slug(model, text: str, *, fallback: str) -> str:
        base = slugify(text) or slugify(fallback)
        slug, n = base, 2
        while model.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug

    def _to_jpeg(self, path: Path) -> bytes:
        if path in self._jpeg_cache:
            return self._jpeg_cache[path]
        from PIL import Image, ImageOps

        if path.suffix.lower() in {".heic", ".heif"} and not self._heif_ready:
            try:
                from pillow_heif import register_heif_opener
            except ImportError as exc:
                raise CommandError("pillow-heif is required for HEIC images: pip install -r requirements.txt") from exc
            register_heif_opener()
            self._heif_ready = True
        with Image.open(path) as img:
            # Shrink before transposing/converting so those copies are small: the
            # full-size decode is the memory peak, which matters on small servers.
            img.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
            img = ImageOps.exif_transpose(img).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
        self._jpeg_cache[path] = buf.getvalue()
        return self._jpeg_cache[path]
