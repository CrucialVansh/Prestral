from __future__ import annotations

from fastapi import HTTPException

from app.config import Settings
from app.models.schemas import (
    Deck,
    QueryMode,
    QueryRequest,
    QueryResponse,
    SourceCitation,
)
from app.services.embeddings import EmbeddingsClient, top_k_similar
from app.services.llm import LLMClient


def _find_component(deck: Deck, component_id: str):
    for slide in deck.slides:
        for comp in slide.components:
            if comp.id == component_id:
                return slide, comp
    return None, None


def _build_anchor(deck: Deck, request: QueryRequest) -> str:
    parts: list[str] = []

    if request.component_id:
        slide, comp = _find_component(deck, request.component_id)
        if comp is None:
            raise HTTPException(status_code=404, detail=f"Component not found: {request.component_id}")
        parts.append(f"Component {comp.id} ({comp.type.value}): {comp.text}")
        if comp.context:
            parts.append(f"Previously linked context: {comp.context}")
        if slide and slide.notes:
            parts.append(f"Slide notes: {slide.notes}")
        return "\n".join(parts)

    if request.slide_index is not None:
        matching = [s for s in deck.slides if s.index == request.slide_index]
        if not matching:
            raise HTTPException(status_code=404, detail=f"Slide not found: {request.slide_index}")
        slide = matching[0]
        parts.append(f"Slide {slide.index}")
        for comp in slide.components:
            line = f"- [{comp.id}] ({comp.type.value}): {comp.text}"
            if comp.context:
                line += f"\n  context: {comp.context}"
            parts.append(line)
        if slide.notes:
            parts.append(f"Notes: {slide.notes}")
        return "\n".join(parts)

    # Whole-deck fallback
    for slide in deck.slides:
        titles = [c.text for c in slide.components if c.type.value == "title" and c.text]
        title = titles[0] if titles else f"Slide {slide.index}"
        parts.append(f"- Slide {slide.index}: {title}")
    return "Deck overview:\n" + "\n".join(parts)


def answer_query(deck: Deck, request: QueryRequest, settings: Settings) -> QueryResponse:
    if request.mode == QueryMode.ASK and not request.question.strip():
        raise HTTPException(status_code=400, detail="question is required when mode is 'ask'")

    anchor = _build_anchor(deck, request)

    # Retrieval query: prefer the user question, else the anchor text.
    retrieval_text = request.question.strip() or anchor
    embeddings = EmbeddingsClient(settings)
    query_vec = embeddings.embed([retrieval_text])[0]
    retrieved = top_k_similar(query_vec, deck.doc_chunks, k=settings.top_k)

    llm = LLMClient(settings)
    answer = llm.answer_query(
        mode=request.mode.value,
        question=request.question,
        anchor_text=anchor,
        retrieved_chunks=retrieved,
    )

    sources = [
        SourceCitation(text=ch.text, source=ch.source) for ch in retrieved
    ]
    return QueryResponse(answer=answer, sources=sources, mode=request.mode)
