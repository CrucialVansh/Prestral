from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import (
    ChatSession,
    ChatSessionSummary,
    CreateSessionRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.chat import get_or_create_session, send_message
from app.store import deck_store, session_store

router = APIRouter(prefix="/api/decks", tags=["sessions"])


@router.post("/{deck_id}/sessions", response_model=ChatSession)
async def create_session(deck_id: str, body: CreateSessionRequest) -> ChatSession:
    """
    Open a chat session for a component.

    By default this is get-or-create on (deck_id, component_id): reopening the
    same hotspot returns the existing session so the user can continue the thread.
    Pass force_new=true to start a fresh session for that component.
    """
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    return get_or_create_session(deck, body)


@router.get("/{deck_id}/sessions", response_model=list[ChatSessionSummary])
async def list_sessions(deck_id: str) -> list[ChatSessionSummary]:
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    return session_store.list_for_deck(deck_id)


@router.get("/{deck_id}/sessions/{session_id}", response_model=ChatSession)
async def get_session(deck_id: str, session_id: str) -> ChatSession:
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    session = session_store.get(session_id)
    if session is None or session.deck_id != deck_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@router.post(
    "/{deck_id}/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
)
async def post_message(
    deck_id: str,
    session_id: str,
    body: SendMessageRequest,
) -> SendMessageResponse:
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    session = session_store.get(session_id)
    if session is None or session.deck_id != deck_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    settings = get_settings()
    try:
        return send_message(deck, session, body, settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Chat message failed: {exc}",
        ) from exc


@router.delete("/{deck_id}/sessions/{session_id}")
async def delete_session(deck_id: str, session_id: str) -> dict[str, bool]:
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    session = session_store.get(session_id)
    if session is None or session.deck_id != deck_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    session_store.delete(session_id)
    return {"deleted": True}
