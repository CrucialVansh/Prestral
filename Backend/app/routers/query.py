"""Single-shot ask / summarize / explain (no conversation history)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from app.config import get_settings
from app.models.schemas import QueryRequest, QueryResponse
from app.services.qa import answer_query
from app.store import deck_store

router = APIRouter(prefix="/api/decks", tags=["query"])


@router.post(
    "/{deck_id}/query",
    response_model=QueryResponse,
    summary="Single-shot ask / summarize / explain",
    response_description="One-off answer with retrieved source passages.",
    responses={
        400: {"description": "Missing question for ask mode, or bad scope."},
        404: {"description": "Deck / slide / component not found."},
        500: {"description": "Embedding or LLM call failed."},
    },
)
async def query_deck(
    body: QueryRequest,
    deck_id: str = Path(..., description="Deck id from upload/import."),
) -> QueryResponse:
    """
    One-shot Q&A against a deck (no chat history).

    Prefer **sessions** (``POST /api/decks/{deck_id}/sessions/.../messages``) when the
    user will follow up. Use this endpoint for a quick one-off answer.

    Scope (most specific wins):
    - ``component_id`` — focus on one hotspot
    - ``slide_index`` — focus on one slide
    - neither — whole-deck overview

    ``audience`` controls how complex/jargon-heavy the answer is
    (e.g. ``swe``, ``marketing``, ``executive``, or free text).
    """
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")

    settings = get_settings()
    try:
        return answer_query(deck, body, settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {exc}",
        ) from exc
