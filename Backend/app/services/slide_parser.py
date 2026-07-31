from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

from app.models.schemas import BBox, Component, ComponentType, Slide


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
        # Prefer alt text / name for pictures (no OCR in this pipeline).
        name = getattr(shape, "name", "") or ""
        alt = ""
        try:
            cNvPr = shape._element.nvPicPr.cNvPr  # type: ignore[attr-defined]
            alt = cNvPr.get("descr") or ""
        except Exception:
            pass
        return (alt or name).strip()

    if getattr(shape, "has_text_frame", False):
        return (shape.text_frame.text or "").strip()

    return ""


def _extract_notes(slide) -> str:
    try:
        if slide.has_notes_slide and slide.notes_slide:
            return (slide.notes_slide.notes_text_frame.text or "").strip()
    except Exception:
        pass
    return ""


def parse_slides(file_bytes: bytes | BinaryIO) -> list[Slide]:
    """Parse a PPTX into a list of Slide models with normalized component bboxes."""
    stream = BytesIO(file_bytes) if isinstance(file_bytes, (bytes, bytearray)) else file_bytes
    prs = Presentation(stream)
    slide_width = int(prs.slide_width)
    slide_height = int(prs.slide_height)

    slides: list[Slide] = []
    for slide_idx, slide in enumerate(prs.slides):
        components: list[Component] = []
        for shape_idx, shape in enumerate(slide.shapes):
            # Skip tiny / invisible decorative shapes with no useful content.
            text = _extract_text(shape)
            ctype = _component_type(shape)
            if not text and ctype not in {
                ComponentType.PICTURE,
                ComponentType.CHART,
                ComponentType.TABLE,
            }:
                continue

            components.append(
                Component(
                    id=f"slide{slide_idx}-shape{shape_idx}",
                    type=ctype,
                    bbox=_normalize_bbox(shape, slide_width, slide_height),
                    text=text,
                )
            )

        slides.append(
            Slide(
                index=slide_idx,
                notes=_extract_notes(slide),
                components=components,
            )
        )

    return slides
