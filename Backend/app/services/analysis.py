from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
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


def _parse_docs(
    docs: Sequence[tuple[bytes, str]],
    settings: Settings,
) -> tuple[list[DocChunk], list[str]]:
    all_chunks: list[DocChunk] = []
    names: list[str] = []
    for doc_bytes, doc_filename in docs:
        names.append(doc_filename)
        chunks = parse_document(
            doc_bytes,
            doc_filename,
            max_chars=settings.chunk_max_chars,
            overlap=settings.chunk_overlap,
        )
        for chunk in chunks:
            # Prefix so citations stay unique across multiple Drive docs.
            chunk.source = f"{doc_filename}:{chunk.source}"
        all_chunks.extend(chunks)
        if not chunks:
            logger.warning("Document produced zero chunks: %s", doc_filename)
    return all_chunks, names


def analyze_deck_multi(
    *,
    slides_bytes: bytes,
    slides_filename: str,
    docs: Sequence[tuple[bytes, str]],
    settings: Settings,
    source: str = "upload",
) -> Deck:
    """
    Full pipeline over one PPTX and one-or-more grounding documents.
    """
    if not docs:
        raise ValueError("At least one supporting document is required")

    parsed = parse_slides(slides_bytes)
    slides = parsed.slides
    images = parsed.images
    chunks, doc_names = _parse_docs(docs, settings)

    embeddings = EmbeddingsClient(settings)
    llm = LLMClient(settings)

    if chunks:
        embeddings.embed_chunks(chunks)

    for slide in slides:
        slide_images = {
            c.id: images[c.id] for c in slide.components if c.id in images
        }
        retrieved = _retrieve_for_slide(slide, chunks, embeddings, settings.top_k)
        analysis = llm.relate_slide_components(slide, retrieved, images=slide_images)
        _apply_component_contexts(slide.components, analysis)

    return Deck(
        id=str(uuid.uuid4()),
        slides_filename=slides_filename,
        doc_filename=", ".join(doc_names),
        doc_filenames=list(doc_names),
        slides=slides,
        doc_chunks=chunks,
        component_images=images,
        source=source,
    )


def analyze_deck(
    *,
    slides_bytes: bytes,
    slides_filename: str,
    doc_bytes: bytes,
    doc_filename: str,
    settings: Settings,
    source: str = "upload",
) -> Deck:
    """Backward-compatible single-document analysis."""
    return analyze_deck_multi(
        slides_bytes=slides_bytes,
        slides_filename=slides_filename,
        docs=[(doc_bytes, doc_filename)],
        settings=settings,
        source=source,
    )
