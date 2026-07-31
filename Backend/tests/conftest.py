from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document
from pptx import Presentation
from pptx.util import Inches


@pytest.fixture
def sample_pptx_bytes() -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Q3 Revenue Overview"
    slide.placeholders[1].text = (
        "Revenue grew 12% YoY\nDriven by enterprise segment"
    )
    notes = slide.notes_slide
    notes.notes_text_frame.text = "Cover enterprise upsell and new logos."

    # Second slide for multi-slide coverage
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Gross Margin"
    slide2.placeholders[1].text = "Margin expanded 150bps to 72%"

    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_docx_bytes() -> bytes:
    doc = Document()
    doc.add_heading("Q3 Financial Deep Dive", level=1)
    doc.add_paragraph(
        "In Q3, total revenue increased by 12% year-over-year, reaching $48M. "
        "The primary driver was the enterprise segment, which contributed $22M "
        "(+18% YoY) due to successful upsell campaigns and three new logo wins."
    )
    doc.add_paragraph(
        "Consumer revenue was flat at $26M. Gross margin expanded by 150bps to 72% "
        "as cloud infrastructure costs declined following the migration to reserved instances."
    )
    doc.add_paragraph(
        "Looking ahead, management expects continued enterprise momentum in Q4, "
        "with a pipeline of five late-stage opportunities totaling approximately $9M ARR."
    )
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch):
    """FastAPI TestClient with a cleared settings cache."""
    from app.config import get_settings

    get_settings.cache_clear()
    # Import after cache clear so startup Settings() sees current .env
    from app.main import app
    from app.store import deck_store, session_store
    from fastapi.testclient import TestClient

    # Reset in-memory stores between tests
    deck_store.clear()
    session_store.clear()

    with TestClient(app) as c:
        yield c

    deck_store.clear()
    session_store.clear()
    get_settings.cache_clear()
