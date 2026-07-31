"""Multi-turn component chat sessions (switchable by component)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from app.config import get_settings
from app.models.schemas import (
    ChatSession,
    ChatSessionSummary,
    CreateSessionRequest,
    SendMessageRequest,
    SendMessageResponse,
    UpdateSessionRequest,
)
from app.services.chat import get_or_create_session, send_message, update_session
from app.store import deck_store, session_store

router = APIRouter(prefix="/api/decks", tags=["sessions"])


@router.post(
    "/{deck_id}/sessions",
    response_model=ChatSession,
    summary="Open or resume a component chat",
    response_description="Existing or newly created session (empty ``messages`` if new).",
    responses={404: {"description": "Deck or component not found."}},
)
async def create_session(
    body: CreateSessionRequest,
    deck_id: str = Path(..., description="Deck id from upload/import."),
) -> ChatSession:
    """
    Open a chat session for a hotspot.

    **Get-or-create:** reopening the same ``component_id`` returns the same session
    so the user can continue the thread. Pass ``force_new: true`` to start fresh
    (the previous session remains listable).

    ``audience`` (e.g. ``swe``, ``marketing``, or free text) controls explanation
    complexity. If you reopen with a new audience, the existing session is updated.
    """
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    return get_or_create_session(deck, body)


@router.get(
    "/{deck_id}/sessions",
    response_model=list[ChatSessionSummary],
    summary="List sessions for a deck",
    response_description="Newest-updated first — ideal for a session switcher.",
)
async def list_sessions(
    deck_id: str = Path(..., description="Deck id from upload/import."),
) -> list[ChatSessionSummary]:
    """List all chat sessions for this deck (one or more per component over time)."""
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    return session_store.list_for_deck(deck_id)


@router.get(
    "/{deck_id}/sessions/{session_id}",
    response_model=ChatSession,
    summary="Get session + full history",
    responses={404: {"description": "Deck or session not found."}},
)
async def get_session(
    deck_id: str = Path(..., description="Deck id."),
    session_id: str = Path(..., description="Session id from create/list."),
) -> ChatSession:
    """Fetch a session including the full message history for rendering the chat UI."""
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    session = session_store.get(session_id)
    if session is None or session.deck_id != deck_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@router.patch(
    "/{deck_id}/sessions/{session_id}",
    response_model=ChatSession,
    summary="Update session audience/role",
    responses={404: {"description": "Deck or session not found."}},
)
async def patch_session(
    body: UpdateSessionRequest,
    deck_id: str = Path(..., description="Deck id."),
    session_id: str = Path(..., description="Session id."),
) -> ChatSession:
    """
    Change the reader's role without sending a message.

    Subsequent ``/messages`` calls will use the new ``audience`` unless overridden
    per-turn.
    """
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    session = session_store.get(session_id)
    if session is None or session.deck_id != deck_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return update_session(session, body)


@router.post(
    "/{deck_id}/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    summary="Send a chat message",
    response_description="Echo of the user turn plus the assistant reply and sources.",
    responses={
        400: {"description": "Missing content for ask mode."},
        404: {"description": "Deck or session not found."},
        500: {"description": "Embedding or LLM call failed."},
    },
)
async def post_message(
    body: SendMessageRequest,
    deck_id: str = Path(..., description="Deck id."),
    session_id: str = Path(..., description="Session id."),
) -> SendMessageResponse:
    """
    Append a user message and get an assistant reply.

    Prior turns are included automatically (multi-turn). Each turn still retrieves
    relevant doc chunks (RAG) scoped to this session's component.
    """
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


@router.delete(
    "/{deck_id}/sessions/{session_id}",
    summary="Delete a session",
    responses={404: {"description": "Deck or session not found."}},
)
async def delete_session(
    deck_id: str = Path(..., description="Deck id."),
    session_id: str = Path(..., description="Session id to remove."),
) -> dict[str, bool]:
    """Remove a chat session from memory. Does not delete the deck."""
    deck = deck_store.get(deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail=f"Deck not found: {deck_id}")
    session = session_store.get(session_id)
    if session is None or session.deck_id != deck_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    session_store.delete(session_id)
    return {"deleted": True}
