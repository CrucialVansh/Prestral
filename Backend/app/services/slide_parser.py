"""Parse PPTX slides into components; extract embedded picture bytes as data URIs."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import BinaryIO

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

from app.models.schemas import BBox, Component, ComponentType, Slide
from app.services.slide_rasterizer import rasterize_slides_pptx

logger = logging.getLogger(__name__)

_PLACEHOLDER_TITLE_TYPES = {
    PP_PLACEHOLDER.TITLE,
    PP_PLACEHOLDER.CENTER_TITLE,
    PP_PLACEHOLDER.VERTICAL_TITLE,
}

_PLACEHOLDER_BODY_TYPES = {
    PP_PLACEHOLDER.BODY,
    PP_PLACEHOLDER.OBJECT,
    PP_PLACEHOLDER.VERTICAL_BODY,
}

# Native charts / groups / empty decorative shapes are not treated as vision targets.
# Only embedded PICTURE blobs are extracted for multimodal prompting.
_MAX_IMAGES_PER_SLIDE = 8


@dataclass
class ParsedPresentation:
    """Slides plus server-side image map (component_id -> data URI)."""

    slides: list[Slide]
    images: dict[str, str] = field(default_factory=dict)
    slide_images: list[str] = field(default_factory=list)
    aspect_ratio: float | None = None


def _normalize_bbox(shape, slide_width: int, slide_height: int) -> BBox:
    left = float(shape.left or 0) / slide_width
    top = float(shape.top or 0) / slide_height
    width = float(shape.width or 0) / slide_width
    height = float(shape.height or 0) / slide_height
    return BBox(
        left=max(0.0, min(1.0, left)),
        top=max(0.0, min(1.0, top)),
        width=max(0.0, min(1.0, width)),
        height=max(0.0, min(1.0, height)),
    )


def _component_type(shape) -> ComponentType:
    shape_type = shape.shape_type

    if shape_type == MSO_SHAPE_TYPE.PICTURE:
        return ComponentType.PICTURE
    if shape_type == MSO_SHAPE_TYPE.TABLE:
        return ComponentType.TABLE
    if shape_type == MSO_SHAPE_TYPE.CHART:
        return ComponentType.CHART
    if shape_type == MSO_SHAPE_TYPE.GROUP:
        return ComponentType.GROUP

    if getattr(shape, "is_placeholder", False):
        try:
            ph_type = shape.placeholder_format.type
            if ph_type in _PLACEHOLDER_TITLE_TYPES:
                return ComponentType.TITLE
            if ph_type in _PLACEHOLDER_BODY_TYPES:
                return ComponentType.BODY
        except Exception:
            pass

    if shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
        return ComponentType.TEXT_BOX

    if getattr(shape, "has_text_frame", False):
        return ComponentType.TEXT_BOX

    return ComponentType.OTHER


def _picture_label(shape) -> str:
    name = getattr(shape, "name", "") or ""
    alt = ""
    try:
        cNvPr = shape._element.nvPicPr.cNvPr  # type: ignore[attr-defined]
        alt = cNvPr.get("descr") or ""
    except Exception:
        pass
    return (alt or name).strip()


def _extract_text(shape) -> str:
    shape_type = shape.shape_type

    if shape_type == MSO_SHAPE_TYPE.TABLE:
        rows: list[str] = []
        table = shape.table
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)

    if shape_type == MSO_SHAPE_TYPE.PICTURE:
        return _picture_label(shape)

    if getattr(shape, "has_text_frame", False):
        return (shape.text_frame.text or "").strip()

    return ""


def _picture_data_uri(shape) -> str | None:
    """
    Return a ``data:<mime>;base64,...`` URI for an embedded picture only.

    Native charts, auto-shapes, and other stylistic shapes are ignored.
    """
    if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
        return None
    try:
        image = shape.image
        blob = image.blob
        mime = image.content_type or "image/png"
        if not blob:
            return None
        b64 = base64.b64encode(blob).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as exc:
        logger.warning("Could not extract picture blob from shape %s: %s", getattr(shape, "name", "?"), exc)
        return None


def _extract_notes(slide) -> str:
    try:
        if slide.has_notes_slide and slide.notes_slide:
            return (slide.notes_slide.notes_text_frame.text or "").strip()
    except Exception:
        pass
    return ""


def parse_slides(file_bytes: bytes | BinaryIO, rasterize: bool = True) -> ParsedPresentation:
    """
    Parse a PPTX into slides/components and extract embedded picture data URIs.

    Vision / multimodal uses **only** ``MSO_SHAPE_TYPE.PICTURE`` blobs — not charts
    or decorative native shapes. Text/table components are still returned for hotspots.

    Args:
        file_bytes: The PPTX file content
        rasterize: If True, attempt to rasterize each slide to a PNG image.
                   Falls back gracefully if LibreOffice is not available.

    Returns:
        ParsedPresentation with slides, component images, slide images, and aspect ratio.
    """
    stream = BytesIO(file_bytes) if isinstance(file_bytes, (bytes, bytearray)) else file_bytes
    prs = Presentation(stream)
    slide_width = int(prs.slide_width)
    slide_height = int(prs.slide_height)

    # Calculate aspect ratio (width / height)
    aspect_ratio = slide_width / slide_height if slide_height > 0 else None

    slides: list[Slide] = []
    images: dict[str, str] = {}

    # Rasterize slides first (if requested)
    slide_image_urls: list[str] = []
    if rasterize:
        slide_image_urls = rasterize_slides_pptx(file_bytes)
        if slide_image_urls and slide_image_urls[0].startswith("data:image/svg"):
            logger.warning(
                "Slide images are SVG placeholders (install LibreOffice or Pillow for real PNGs)."
            )
        elif slide_image_urls:
            logger.info("Rasterized %d slide image(s)", len(slide_image_urls))

    for slide_idx, slide in enumerate(prs.slides):
        components: list[Component] = []
        images_on_slide = 0

        for shape_idx, shape in enumerate(slide.shapes):
            ctype = _component_type(shape)

            # Skip empty decorative / stylistic shapes (no text, not a picture/table).
            # Charts are kept as hotspots if present, but we do not extract image bytes.
            text = _extract_text(shape)
            if not text and ctype not in {ComponentType.PICTURE, ComponentType.TABLE}:
                continue
            # Skip chart-only shapes with no text — not images, not useful text hotspots.
            if ctype == ComponentType.CHART and not text:
                continue
            if ctype in {ComponentType.GROUP, ComponentType.OTHER} and not text:
                continue

            component_id = f"slide{slide_idx}-shape{shape_idx}"
            has_image = False

            if ctype == ComponentType.PICTURE and images_on_slide < _MAX_IMAGES_PER_SLIDE:
                data_uri = _picture_data_uri(shape)
                if data_uri:
                    images[component_id] = data_uri
                    has_image = True
                    images_on_slide += 1

            components.append(
                Component(
                    id=component_id,
                    type=ctype,
                    bbox=_normalize_bbox(shape, slide_width, slide_height),
                    text=text,
                    has_image=has_image,
                )
            )

        # Get the slide image URL (uses placeholder if rasterization failed)
        slide_image_url = slide_image_urls[slide_idx] if slide_idx < len(slide_image_urls) else None

        slides.append(
            Slide(
                index=slide_idx,
                notes=_extract_notes(slide),
                components=components,
                image_url=slide_image_url,
            )
        )

    return ParsedPresentation(
        slides=slides,
        images=images,
        slide_images=slide_image_urls,
        aspect_ratio=aspect_ratio,
    )
