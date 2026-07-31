from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import Settings
from app.models.schemas import Component, Deck, DocChunk, Slide
from app.services.doc_parser import parse_document
from app.services.embeddings import EmbeddingsClient, top_k_similar
from app.services.llm import LLMClient
from app.services.slide_parser import parse_slides

logger = logging.getLogger(__name__)


def _apply_component_contexts(
    components: list[Component],
    analysis: dict[str, Any],
) -> None:
    for comp in components:
        entry = analysis.get(comp.id)
        if not isinstance(entry, dict):
            continue
        context = entry.get("context")
        sources = entry.get("sources")
        if isinstance(context, str):
            comp.context = context
        if isinstance(sources, list):
            comp.sources = [str(s) for s in sources]


def _collect_slide_query_text(slide: Slide) -> str:
    parts = [c.text for c in slide.components if c.text]
    if slide.notes:
        parts.append(slide.notes)
    return "\n".join(parts)


def _retrieve_for_slide(
    slide: Slide,
    chunks: list[DocChunk],
    embeddings: EmbeddingsClient,
    top_k: int,
) -> list[DocChunk]:
    """Retrieve a union of top-k chunks for the whole slide and each component."""
    seen: set[str] = set()
    results: list[DocChunk] = []

    queries: list[str] = []
    slide_text = _collect_slide_query_text(slide)
    if slide_text.strip():
        queries.append(slide_text)
    for comp in slide.components:
        if comp.text.strip():
            queries.append(comp.text)

    if not queries:
        return chunks[:top_k]

    vectors = embeddings.embed(queries)
    for vec in vectors:
        for ch in top_k_similar(vec, chunks, k=top_k):
            key = f"{ch.source}:{ch.text[:80]}"
            if key not in seen:
                seen.add(key)
                results.append(ch)

    return results


def analyze_deck(
    *,
    slides_bytes: bytes,
    slides_filename: str,
    doc_bytes: bytes,
    doc_filename: str,
    settings: Settings,
) -> Deck:
    """
    Full pipeline:
      1. Parse slides into components with normalized bboxes
      2. Parse + chunk the supporting document
      3. Embed doc chunks
      4. Per slide: retrieve relevant chunks, call LLM to relate each component
      5. Return a Deck ready for storage / API response
    """
    slides = parse_slides(slides_bytes)
    chunks = parse_document(
        doc_bytes,
        doc_filename,
        max_chars=settings.chunk_max_chars,
        overlap=settings.chunk_overlap,
    )

    embeddings = EmbeddingsClient(settings)
    llm = LLMClient(settings)

    if chunks:
        embeddings.embed_chunks(chunks)
    else:
        logger.warning("Document produced zero chunks: %s", doc_filename)

    for slide in slides:
        retrieved = _retrieve_for_slide(slide, chunks, embeddings, settings.top_k)
        analysis = llm.relate_slide_components(slide, retrieved)
        _apply_component_contexts(slide.components, analysis)

    deck = Deck(
        id=str(uuid.uuid4()),
        slides_filename=slides_filename,
        doc_filename=doc_filename,
        slides=slides,
        doc_chunks=chunks,
    )
    return deck
