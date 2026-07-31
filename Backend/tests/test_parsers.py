from __future__ import annotations

from app.services.doc_parser import parse_document
from app.services.slide_parser import parse_slides


def test_parse_slides_extracts_components_and_notes(sample_pptx_bytes: bytes) -> None:
    slides = parse_slides(sample_pptx_bytes)

    assert len(slides) == 2
    assert slides[0].index == 0
    assert "enterprise" in slides[0].notes.lower() or "upsell" in slides[0].notes.lower()

    titles = [c for c in slides[0].components if c.type.value == "title"]
    assert titles
    assert "Q3 Revenue" in titles[0].text

    for comp in slides[0].components:
        assert 0.0 <= comp.bbox.left <= 1.0
        assert 0.0 <= comp.bbox.top <= 1.0
        assert 0.0 <= comp.bbox.width <= 1.0
        assert 0.0 <= comp.bbox.height <= 1.0
        assert comp.id.startswith("slide0-")


def test_parse_docx_chunks(sample_docx_bytes: bytes) -> None:
    chunks = parse_document(sample_docx_bytes, "notes.docx")

    assert len(chunks) >= 2
    joined = " ".join(c.text for c in chunks)
    assert "12%" in joined
    assert "gross margin" in joined.lower() or "150bps" in joined
    assert all(c.source for c in chunks)


def test_health(client) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_upload_rejects_bad_extensions(
    client, sample_pptx_bytes: bytes, sample_docx_bytes: bytes
) -> None:
    res = client.post(
        "/api/decks/upload",
        files={
            "slides": ("deck.pdf", sample_pptx_bytes, "application/pdf"),
            "doc": ("notes.docx", sample_docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        },
    )
    assert res.status_code == 400
    assert "pptx" in res.json()["detail"].lower()

    res = client.post(
        "/api/decks/upload",
        files={
            "slides": ("deck.pptx", sample_pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            "doc": ("notes.txt", sample_docx_bytes, "text/plain"),
        },
    )
    assert res.status_code == 400
    assert "docx" in res.json()["detail"].lower() or "pdf" in res.json()["detail"].lower()
