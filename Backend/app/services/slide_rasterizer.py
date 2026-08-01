"""Rasterize PPTX slides to PNG images.

Primary: LibreOffice → PDF → PyMuPDF PNG (best fidelity).
Fallback: Pillow compositor from python-pptx shapes (no LibreOffice required).
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

try:
    import fitz  # PyMuPDF

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUPINFO.wShowWindow = subprocess.SW_HIDE
    _CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    _STARTUPINFO = None
    _CREATE_NO_WINDOW = 0

# Legacy SVG placeholder (only if Pillow is also missing)
TRANSPARENT_PNG_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" '
    'viewBox="0 0 1920 1080">'
    '<rect width="1920" height="1080" fill="#f3efe6"/>'
    '<text x="960" y="540" text-anchor="middle" fill="#999" '
    'font-family="Arial, sans-serif" font-size="36">Slide</text>'
    "</svg>"
)
TRANSPARENT_PNG = base64.b64encode(TRANSPARENT_PNG_SVG.encode()).decode()

_soffice_path: str | None = None
DEFAULT_WIDTH_PX = 1920


def _find_soffice() -> str | None:
    """Find the soffice executable. Returns None if not found."""
    custom_path = os.environ.get("LIBREOFFICE_PATH")
    if custom_path and os.path.isfile(custom_path):
        logger.info("Using custom LibreOffice path: %s", custom_path)
        return custom_path

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found

    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/usr/lib/libreoffice/program/soffice",
    ]
    if sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates.extend(
            [
                os.path.join(program_files, "LibreOffice", "program", "soffice.exe"),
                os.path.join(program_files + " (x86)", "LibreOffice", "program", "soffice.exe"),
            ]
        )

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _check_libreoffice() -> bool:
    global _soffice_path
    soffice_cmd = _find_soffice()
    if not soffice_cmd:
        logger.warning(
            "LibreOffice not found. Set LIBREOFFICE_PATH or install LibreOffice. "
            "Falling back to Pillow slide compositor."
        )
        return False
    _soffice_path = soffice_cmd
    logger.info("Found LibreOffice at: %s", soffice_cmd)
    return True


def _png_data_uri(png_bytes: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"


def _placeholder_uris(count: int) -> list[str]:
    return [f"data:image/svg+xml;base64,{TRANSPARENT_PNG}" for _ in range(max(1, count))]


def rasterize_slides_pptx(
    file_bytes: bytes | BinaryIO,
    output_dir: Path | str | None = None,
    dpi: int = 150,
) -> list[str]:
    """
    Convert a PPTX to per-slide PNG data URIs.

    Tries LibreOffice first; on failure uses a Pillow shape compositor so
    hotspots still have a real slide image behind them.
    """
    raw = file_bytes if isinstance(file_bytes, (bytes, bytearray)) else file_bytes.read()

    if _check_libreoffice():
        try:
            return _rasterize_via_libreoffice(raw, dpi=dpi)
        except Exception as exc:
            logger.warning("LibreOffice rasterization failed (%s); using compositor", exc)

    if HAS_PIL:
        try:
            uris = _rasterize_via_compositor(raw, width_px=DEFAULT_WIDTH_PX)
            logger.info("Rendered %d slides via Pillow compositor", len(uris))
            return uris
        except Exception as exc:
            logger.warning("Pillow compositor failed: %s", exc)

    try:
        slide_count = len(Presentation(BytesIO(raw)).slides)
    except Exception:
        slide_count = 1
    logger.warning("Using SVG placeholders for %d slides", slide_count)
    return _placeholder_uris(slide_count)


def _rasterize_via_libreoffice(pptx_bytes: bytes, *, dpi: int) -> list[str]:
    global _soffice_path
    soffice_cmd = _soffice_path
    if not soffice_cmd:
        raise RuntimeError("LibreOffice path not set")

    with tempfile.TemporaryDirectory(prefix="prestral-slides-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        pptx_path = tmpdir_path / "presentation.pptx"
        pptx_path.write_bytes(pptx_bytes)
        pdf_path = tmpdir_path / "presentation.pdf"

        cmd = [
            soffice_cmd,
            "--headless",
            "--nologo",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmpdir_path),
            str(pptx_path),
        ]
        kwargs: dict = {
            "args": cmd,
            "capture_output": True,
            "text": True,
            "timeout": 180,
        }
        if sys.platform == "win32":
            kwargs["startupinfo"] = _STARTUPINFO
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        result = subprocess.run(**kwargs)
        if result.returncode != 0 or not pdf_path.exists():
            raise RuntimeError(
                f"LibreOffice PDF conversion failed (exit {result.returncode}): "
                f"{result.stderr or result.stdout or 'no output'}"
            )

        if not HAS_PYMUPDF:
            raise RuntimeError("PyMuPDF is required to render LibreOffice PDF pages")

        doc = fitz.open(str(pdf_path))
        try:
            data_uris: list[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                data_uris.append(_png_data_uri(pix.tobytes("png")))
            return data_uris
        finally:
            doc.close()


def _emu_rgb(rgb) -> tuple[int, int, int] | None:
    if rgb is None:
        return None
    try:
        return (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except Exception:
        return None


def _shape_fill_rgb(shape) -> tuple[int, int, int] | None:
    try:
        from pptx.enum.dml import MSO_FILL

        fill = shape.fill
        if fill.type == MSO_FILL.SOLID:
            return _emu_rgb(fill.fore_color.rgb)
    except Exception:
        return None
    return None


def _slide_background_rgb(slide) -> tuple[int, int, int]:
    try:
        from pptx.enum.dml import MSO_FILL

        fill = slide.background.fill
        if fill.type == MSO_FILL.SOLID:
            rgb = _emu_rgb(fill.fore_color.rgb)
            if rgb:
                return rgb
    except Exception:
        pass
    return (255, 255, 255)


def _font(size: int) -> ImageFont.ImageFont:
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _iter_shapes(shapes):
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_shapes(shape.shapes)
        else:
            yield shape


def _draw_text_frame(
    draw: ImageDraw.ImageDraw,
    shape,
    box: tuple[int, int, int, int],
    scale: float,
) -> None:
    left, top, right, bottom = box
    max_w = max(1, right - left - 8)
    y = top + 4
    try:
        for para in shape.text_frame.paragraphs:
            runs_text = "".join(run.text or "" for run in para.runs) or (para.text or "")
            if not runs_text.strip():
                y += 8
                continue
            font_size_pt = 18
            for run in para.runs:
                if run.font.size:
                    font_size_pt = max(8, int(run.font.size.pt))
                    break
            # 1pt = 12700 EMU; scale is px/EMU
            px = max(10, int(font_size_pt * 12700 * scale))
            font = _font(px)
            words = runs_text.split()
            line = ""
            for word in words:
                trial = f"{line} {word}".strip()
                if draw.textlength(trial, font=font) <= max_w or not line:
                    line = trial
                else:
                    draw.text((left + 4, y), line, fill=(30, 30, 30), font=font)
                    y += int(px * 1.25)
                    if y > bottom - px:
                        return
                    line = word
            if line:
                draw.text((left + 4, y), line, fill=(30, 30, 30), font=font)
                y += int(px * 1.35)
            if y > bottom - 4:
                return
    except Exception as exc:
        logger.debug("Text draw failed: %s", exc)


def _rasterize_via_compositor(pptx_bytes: bytes, *, width_px: int) -> list[str]:
    if not HAS_PIL:
        raise RuntimeError("Pillow is required for the slide compositor fallback")

    prs = Presentation(BytesIO(pptx_bytes))
    slide_w = int(prs.slide_width) or 1
    slide_h = int(prs.slide_height) or 1
    height_px = max(1, int(round(width_px * slide_h / slide_w)))
    scale = width_px / slide_w

    uris: list[str] = []
    for slide in prs.slides:
        bg = _slide_background_rgb(slide)
        img = Image.new("RGB", (width_px, height_px), bg)
        draw = ImageDraw.Draw(img)

        for shape in _iter_shapes(slide.shapes):
            left = int((shape.left or 0) * scale)
            top = int((shape.top or 0) * scale)
            width = max(1, int((shape.width or 0) * scale))
            height = max(1, int((shape.height or 0) * scale))
            box = (left, top, left + width, top + height)

            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    blob = shape.image.blob
                    pic = Image.open(BytesIO(blob)).convert("RGBA")
                    pic = pic.resize((width, height), Image.Resampling.LANCZOS)
                    img.paste(pic, (left, top), pic)
                except Exception as exc:
                    logger.debug("Skip picture paste: %s", exc)
                    draw.rectangle(box, outline=(180, 180, 180), width=1)
                continue

            fill = _shape_fill_rgb(shape)
            if fill:
                draw.rectangle(box, fill=fill)

            if getattr(shape, "has_text_frame", False):
                _draw_text_frame(draw, shape, box, scale)

        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        uris.append(_png_data_uri(buf.getvalue()))

    return uris


def rasterize_slides_pptx_to_files(
    file_bytes: bytes | BinaryIO,
    output_dir: Path | str,
    dpi: int = 150,
) -> list[Path]:
    """Write per-slide PNGs to disk (LibreOffice preferred, compositor fallback)."""
    uris = rasterize_slides_pptx(file_bytes, dpi=dpi)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, uri in enumerate(uris):
        path = out / f"slide_{i}.png"
        if uri.startswith("data:image/png;base64,"):
            path.write_bytes(base64.b64decode(uri.split(",", 1)[1]))
        else:
            # SVG placeholder → still write a tiny PNG via compositor count
            if HAS_PIL:
                Image.new("RGB", (400, 300), (240, 240, 240)).save(path, format="PNG")
            else:
                path.write_bytes(b"")
        paths.append(path)
    return paths
