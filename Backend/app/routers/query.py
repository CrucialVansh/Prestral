from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import QueryRequest, QueryResponse
from app.services.qa import answer_query
from app.store import deck_store

router = APIRouter(prefix="/api/decks", tags=["query"])


@router.post("/{deck_id}/query", response_model=QueryResponse)
async def query_deck(deck_id: str, body: QueryRequest) -> QueryResponse:
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
