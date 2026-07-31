"""Deck upload and retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Path, UploadFile

from app.config import get_settings
from app.models.schemas import DeckAnalysisResponse, DeckSummary
from app.services.analysis import analyze_deck
from app.store import deck_store

router = APIRouter(prefix="/api/decks", tags=["decks"])

ALLOWED_SLIDE_EXTS = {".pptx"}
ALLOWED_DOC_EXTS = {".docx", ".pdf"}


def _ext(filename: str) -> str:
    name = filename.lower()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1]


def _to_response(deck) -> DeckAnalysisResponse:
    """Map an internal Deck to the public analysis payload."""
    return DeckAnalysisResponse(
        id=deck.id,
        slides_filename=deck.slides_filename,
        doc_filename=deck.doc_filename,
        doc_filenames=deck.doc_filenames or (
            [deck.doc_filename] if deck.doc_filename else []
        ),
        slides=deck.slides,
        source=getattr(deck, "source", "upload"),
        selected_docs=[],
    )


@router.post(
    "/upload",
    response_model=DeckAnalysisResponse,
    summary="Upload slides + supporting doc",
    response_description="Analyzed deck with per-component bbox, text, and doc-grounded context.",
    responses={
        400: {"description": "Invalid file type or empty upload."},
        500: {"description": "Parse / embedding / LLM pipeline failed."},
    },
)
async def upload_deck(
    slides: UploadFile = File(..., description="PowerPoint deck (``.pptx`` only)."),
    doc: UploadFile = File(..., description="Supporting document (``.docx`` or ``.pdf``)."),
) -> DeckAnalysisResponse:
    """
    Upload a local PPTX and one supporting document.

    The server:
    1. Parses every slide shape into a **component** (id, type, normalized bbox, text)
    2. Chunks + embeds the document
    3. Uses Mistral to attach ``context`` / ``sources`` to each component

    Store the returned ``id`` — you need it for query, sessions, and refetch.

    For Google Drive files, use ``POST /api/storage/import`` instead.
    """
    slides_name = slides.filename or "slides.pptx"
    doc_name = doc.filename or "document.docx"

    if _ext(slides_name) not in ALLOWED_SLIDE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Slides must be .pptx (got '{slides_name}')",
        )
    if _ext(doc_name) not in ALLOWED_DOC_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Document must be .docx or .pdf (got '{doc_name}')",
        )

    slides_bytes = await slides.read()
    doc_bytes = await doc.read()

    if not slides_bytes:
        raise HTTPException(status_code=400, detail="Slides file is empty")
    if not doc_bytes:
        raise HTTPException(status_code=400, detail="Document file is empty")

    settings = get_settings()
    try:
        deck = analyze_deck(
            slides_bytes=slides_bytes,
            slides_filename=slides_name,
            doc_bytes=doc_bytes,
            doc_filename=doc_name,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze deck: {exc}",
        ) from exc

    deck_store.put(deck)
    return _to_response(deck)


@router.get(
    "",
    response_model=list[DeckSummary],
    summary="List processed decks",
    response_description="In-memory decks available until the server restarts.",
)
async def list_decks() -> list[DeckSummary]:
    """Return all decks currently held in memory (id, filenames, slide count)."""
    return deck_store.list()


@router.get(
    "/{deck_id}",
    response_model=DeckAnalysisResponse,
    summary="Get a processed deck",
    responses={404: {"description": "Unknown deck id (or server restarted)."}},
)
async def get_deck(
    deck_id: str = Path(..., description="Deck id returned by upload or Drive import."),
) -> DeckAnalysisResponse:
    """
    Re-fetch a previously analyzed deck (same shape as the upload response).

    Use this when navigating back to a deck without re-uploading.
    """
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    return _to_response(deck)
