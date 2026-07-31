from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import Settings
from app.models.schemas import (
    ChatMessage,
    ChatRole,
    ChatSession,
    CreateSessionRequest,
    Deck,
    QueryMode,
    QueryRequest,
    SendMessageRequest,
    SendMessageResponse,
    SourceCitation,
)
from app.services.embeddings import EmbeddingsClient, top_k_similar
from app.services.llm import LLMClient
from app.services.qa import _build_anchor, _find_component
from app.store import session_store


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_title(comp_text: str, component_id: str) -> str:
    text = (comp_text or "").strip().replace("\n", " ")
    if not text:
        return component_id
    return text if len(text) <= 60 else text[:57] + "..."


def get_or_create_session(
    deck: Deck,
    body: CreateSessionRequest,
) -> ChatSession:
    slide, comp = _find_component(deck, body.component_id)
    if comp is None:
        raise HTTPException(status_code=404, detail=f"Component not found: {body.component_id}")

    if not body.force_new:
        existing = session_store.get_by_component(deck.id, body.component_id)
        if existing is not None:
            return existing

    now = _utc_now()
    session = ChatSession(
        id=str(uuid.uuid4()),
        deck_id=deck.id,
        component_id=comp.id,
        slide_index=slide.index if slide else 0,
        title=_session_title(comp.text, comp.id),
        messages=[],
        created_at=now,
        updated_at=now,
    )
    # force_new: still index by component so "current" session for that hotspot is this one
    session_store.put(session, index_component=True)
    return session


def send_message(
    deck: Deck,
    session: ChatSession,
    body: SendMessageRequest,
    settings: Settings,
) -> SendMessageResponse:
    if body.mode == QueryMode.ASK and not body.content.strip():
        raise HTTPException(status_code=400, detail="content is required when mode is 'ask'")

    # Build the same component anchor the single-shot query uses.
    anchor = _build_anchor(
        deck,
        QueryRequest(
            question=body.content,
            mode=body.mode,
            component_id=session.component_id,
            slide_index=session.slide_index,
        ),
    )

    retrieval_text = body.content.strip() or anchor
    embeddings = EmbeddingsClient(settings)
    query_vec = embeddings.embed([retrieval_text])[0]
    retrieved = top_k_similar(query_vec, deck.doc_chunks, k=settings.top_k)
    sources = [SourceCitation(text=ch.text, source=ch.source) for ch in retrieved]

    history = [
        {"role": m.role.value, "content": m.content}
        for m in session.messages
    ]

    llm = LLMClient(settings)
    answer = llm.answer_chat(
        mode=body.mode.value,
        question=body.content,
        anchor_text=anchor,
        retrieved_chunks=retrieved,
        history=history,
    )

    now = _utc_now()
    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        role=ChatRole.USER,
        content=body.content.strip()
        or (
            "Summarize this component"
            if body.mode == QueryMode.SUMMARIZE
            else "Explain this component"
            if body.mode == QueryMode.EXPLAIN
            else body.content
        ),
        mode=body.mode,
        sources=[],
        created_at=now,
    )
    assistant_msg = ChatMessage(
        id=str(uuid.uuid4()),
        role=ChatRole.ASSISTANT,
        content=answer,
        mode=body.mode,
        sources=sources,
        created_at=_utc_now(),
    )

    session.messages.append(user_msg)
    session.messages.append(assistant_msg)
    session.updated_at = assistant_msg.created_at
    session_store.put(session, index_component=True)

    return SendMessageResponse(
        session_id=session.id,
        user_message=user_msg,
        assistant_message=assistant_msg,
    )
