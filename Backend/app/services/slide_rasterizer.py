"""Rasterize PPTX slides to PNG images using LibreOffice."""

from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

try:
    import fitz  # PyMuPDF - for rendering PDF pages to PNG
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

logger = logging.getLogger(__name__)

# For Windows: prevent console window from popping up when LibreOffice starts
if sys.platform == "win32":
    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _STARTUPINFO.wShowWindow = subprocess.SW_HIDE
    _CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    _STARTUPINFO = None
    _CREATE_NO_WINDOW = 0

# SVG placeholder - light grey rectangle with "Slide" text
# Visible when LibreOffice is not available for slide rasterization
# Using SVG which is smaller than PNG and always works
TRANSPARENT_PNG_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" '
    'viewBox="0 0 400 300">'
    '<rect width="400" height="300" fill="#e0e0e0"/>'
    '<text x="200" y="150" text-anchor="middle" fill="#999" '
    'font-family="Arial, sans-serif" font-size="20">Slide Image</text>'
    '</svg>'
)

# Encode as base64 for data URI
TRANSPARENT_PNG = base64.b64encode(TRANSPARENT_PNG_SVG.encode()).decode()

# Cache for the found soffice path
_soffice_path: str | None = None


def _find_soffice() -> str | None:
    """Find the soffice executable path. Returns None if not found."""
    import platform
    
    # Check for custom path via environment variable
    custom_path = os.environ.get("LIBREOFFICE_PATH")
    if custom_path and os.path.exists(custom_path):
        logger.info("Using custom LibreOffice path: %s", custom_path)
        return custom_path
    
    # Try common LibreOffice paths on Windows
    soffice_paths = ["soffice"]
    if platform.system() == "Windows":
        # Common Windows installation paths
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        soffice_paths.extend([
            os.path.join(program_files, "LibreOffice", "program", "soffice.exe"),
            os.path.join(program_files, "LibreOffice", "program", "soffice"),
            os.path.join(program_files + " (x86)", "LibreOffice", "program", "soffice.exe"),
        ])
    
    for soffice_cmd in soffice_paths:
        if os.path.exists(soffice_cmd):
            return soffice_cmd
    
    return None


def _check_libreoffice() -> bool:
    """Check if LibreOffice is available on the system."""
    global _soffice_path
    
    # Try to find soffice executable
    soffice_cmd = _find_soffice()
    if not soffice_cmd:
        logger.warning(
            "LibreOffice not found. Set LIBREOFFICE_PATH in .env or install LibreOffice. "
            "Searched: PATH, common Windows paths."
        )
        return False
    
    # Check if the executable exists and is a file
    # We don't actually need to run --version; just knowing the path exists is enough
    # The actual conversion will handle errors
    if os.path.isfile(soffice_cmd):
        logger.info("Found LibreOffice at: %s", soffice_cmd)
        _soffice_path = soffice_cmd  # Cache it
        return True
    else:
        logger.warning("LibreOffice path not found or not a file: %s", soffice_cmd)
        return False


def rasterize_slides_pptx(
    file_bytes: bytes | BinaryIO,
    output_dir: Path | str | None = None,
    dpi: int = 150,
) -> list[str]:
    """
    Convert a PPTX file to PNG images, one per slide.

    Uses LibreOffice to convert PPTX to PDF (preserving all slides as pages),
    then uses PyMuPDF (fitz) to render each PDF page as a PNG.

    Args:
        file_bytes: The PPTX file content
        output_dir: Temporary directory for intermediate files (cleaned up automatically)
        dpi: Resolution for the output images

    Returns:
        List of data URIs (PNG format) for each slide, in order.

    Raises:
        RuntimeError: If LibreOffice is not installed or conversion fails.
    """
    global _soffice_path
    
    # Ensure we have the soffice path (might be cached from _check_libreoffice)
    if _soffice_path is None:
        if not _check_libreoffice():
            raise RuntimeError(
                "LibreOffice is required for slide rasterization. "
                "Install from https://www.libreoffice.org/ and ensure 'soffice' is in PATH. "
                "On Windows, also try: set LIBREOFFICE_PATH=C:\\Program Files\\LibreOffice\\program\\soffice.exe"
            )
    
    # Use the cached path
    soffice_cmd = _soffice_path

    # Create a temporary directory for this conversion
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write the PPTX to a temp file
        pptx_path = tmpdir_path / "presentation.pptx"
        if isinstance(file_bytes, bytes):
            pptx_path.write_bytes(file_bytes)
        else:
            with open(pptx_path, "wb") as f:
                shutil.copyfileobj(file_bytes, f)

        pdf_path = tmpdir_path / "presentation.pdf"

        # Step 1: Convert PPTX to PDF using LibreOffice
        # This preserves all slides as individual pages in the PDF
        cmd = [
            soffice_cmd,
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmpdir_path),
            str(pptx_path),
        ]

        try:
            kwargs = {
                "args": cmd,
                "capture_output": True,
                "text": True,
                "timeout": 120,
            }
            if sys.platform == "win32":
                kwargs["startupinfo"] = _STARTUPINFO
                kwargs["creationflags"] = _CREATE_NO_WINDOW
            result = subprocess.run(**kwargs)

            if result.returncode != 0:
                logger.error("LibreOffice PDF conversion failed: %s", result.stderr)
                raise RuntimeError(f"LibreOffice PDF conversion failed: {result.stderr}")

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"LibreOffice PDF conversion timed out: {exc}") from exc

        # Check if PDF was created
        if not pdf_path.exists():
            raise RuntimeError("LibreOffice failed to create PDF file")

        # Step 2: Convert each PDF page to PNG using PyMuPDF (fitz)
        # This is necessary because LibreOffice's --convert-to png only exports
        # the first page/slide, but PDF preserves all slides as pages
        if HAS_PYMUPDF:
            try:
                doc = fitz.open(str(pdf_path))
                data_uris: list[str] = []
                
                for i, page in enumerate(doc):
                    # Render page as a pixmap with the specified DPI
                    pix = page.get_pixmap(dpi=dpi)
                    # Convert to bytes and encode as data URI
                    png_data = pix.tobytes()
                    encoded = base64.b64encode(png_data).decode("ascii")
                    data_uri = f"data:image/png;base64,{encoded}"
                    data_uris.append(data_uri)
                
                # Close the document to release file handles
                doc.close()
                return data_uris
            except Exception as exc:
                logger.warning("PyMuPDF conversion failed: %s. Falling back to placeholder images.", exc)
        else:
            logger.warning("PyMuPDF not installed. Falling back to placeholder images.")

        # Fallback: If PyMuPDF is not available or conversion failed,
        # we need to determine the number of slides from the PPTX directly
        # For now, return a single placeholder image
        logger.warning("Slide rasterization failed. Using placeholder images.")
        
        # Try to get slide count from PPTX to return correct number of placeholders
        try:
            from pptx import Presentation
            prs = Presentation(str(pptx_path))
            slide_count = len(prs.slides)
        except Exception:
            slide_count = 1
        
        return [f"data:image/svg+xml;base64,{TRANSPARENT_PNG}" for _ in range(slide_count)]


def rasterize_slides_pptx_to_files(
    file_bytes: bytes | BinaryIO,
    output_dir: Path | str,
    dpi: int = 150,
) -> list[Path]:
    """
    Convert a PPTX file to PNG image files on disk.

    Uses LibreOffice to convert PPTX to PDF (preserving all slides as pages),
    then uses PyMuPDF (fitz) to render each PDF page as a PNG file.

    Args:
        file_bytes: The PPTX file content
        output_dir: Directory where PNG files will be saved
        dpi: Resolution for the output images

    Returns:
        List of Path objects to the generated PNG files, in order.

    Raises:
        RuntimeError: If LibreOffice is not installed or conversion fails.
    """
    global _soffice_path
    
    # Ensure we have the soffice path
    if _soffice_path is None:
        if not _check_libreoffice():
            raise RuntimeError(
                "LibreOffice is required for slide rasterization. "
                "Install from https://www.libreoffice.org/ and ensure 'soffice' is in PATH. "
                "On Windows, also try: set LIBREOFFICE_PATH=C:\\Program Files\\LibreOffice\\program\\soffice.exe"
            )
    
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # Create a temporary directory for conversion
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write the PPTX to a temp file
        pptx_path = tmpdir_path / "presentation.pptx"
        if isinstance(file_bytes, bytes):
            pptx_path.write_bytes(file_bytes)
        else:
            with open(pptx_path, "wb") as f:
                shutil.copyfileobj(file_bytes, f)

        pdf_path = tmpdir_path / "presentation.pdf"

        # Step 1: Convert PPTX to PDF using LibreOffice
        # Use the cached soffice path
        soffice_cmd = _soffice_path
        cmd = [
            soffice_cmd,
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--convert-to",
            "pdf",
            "--outdir",
            str(tmpdir_path),
            str(pptx_path),
        ]

        try:
            kwargs = {
                "args": cmd,
                "capture_output": True,
                "text": True,
                "timeout": 120,
            }
            if sys.platform == "win32":
                kwargs["startupinfo"] = _STARTUPINFO
                kwargs["creationflags"] = _CREATE_NO_WINDOW
            result = subprocess.run(**kwargs)

            if result.returncode != 0:
                logger.error("LibreOffice PDF conversion failed: %s", result.stderr)
                raise RuntimeError(f"LibreOffice PDF conversion failed: {result.stderr}")

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"LibreOffice PDF conversion timed out: {exc}") from exc

        # Check if PDF was created
        if not pdf_path.exists():
            raise RuntimeError("LibreOffice failed to create PDF file")

        # Step 2: Convert each PDF page to PNG using PyMuPDF (fitz)
        if not HAS_PYMUPDF:
            raise RuntimeError("PyMuPDF is required for slide rasterization. Install with: pip install pymupdf")
        
        try:
            doc = fitz.open(str(pdf_path))
            final_paths: list[Path] = []
            
            for i, page in enumerate(doc):
                # Render page as a pixmap with the specified DPI
                pix = page.get_pixmap(dpi=dpi)
                # Save as PNG
                final_path = output_dir_path / f"slide_{i}.png"
                with open(final_path, "wb") as f:
                    f.write(pix.tobytes())
                final_paths.append(final_path)
            
            # Close the document to release file handles
            doc.close()
            return final_paths
        except Exception as exc:
            raise RuntimeError(f"PyMuPDF conversion failed: {exc}") from exc
