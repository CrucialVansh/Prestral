from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from app.config import Settings
from app.models.schemas import DriveFileInfo
from app.services.doc_parser import parse_document
from app.services.embeddings import EmbeddingsClient
from app.services.google_drive import download_file
from app.services.slide_parser import parse_slides

logger = logging.getLogger(__name__)


@dataclass
class RankedDoc:
    info: DriveFileInfo
    file_bytes: bytes
    preview_text: str
    score: float


def _slide_corpus_text(slides_bytes: bytes) -> str:
    parsed = parse_slides(slides_bytes)
    parts: list[str] = []
    for slide in parsed.slides:
        if slide.notes:
            parts.append(slide.notes)
        for comp in slide.components:
            if comp.text:
                parts.append(comp.text)
    return "\n".join(parts)


def _doc_preview(file_bytes: bytes, filename: str, max_chars: int) -> str:
    try:
        chunks = parse_document(file_bytes, filename, max_chars=max_chars, overlap=0)
    except Exception as exc:
        logger.warning("Could not preview %s: %s", filename, exc)
        return filename
    text = "\n".join(c.text for c in chunks)
    return (text[:max_chars] if text else filename).strip() or filename


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-12
    return float(va @ vb / denom)


def rank_and_select_docs(
    *,
    access_token: str,
    slides_bytes: bytes,
    candidate_docs: list[DriveFileInfo],
    settings: Settings,
    max_docs: int,
) -> list[RankedDoc]:
    """
    Download candidate docs, embed a short preview of each against the slide corpus,
    and return the top-k most relevant documents for RAG grounding.
    """
    if not candidate_docs:
        return []

    max_docs = max(1, max_docs)
    corpus = _slide_corpus_text(slides_bytes)
    if not corpus.strip():
        corpus = "presentation slides"

    embeddings = EmbeddingsClient(settings)
    query_vec = embeddings.embed([corpus[: settings.drive_preview_chars]])[0]

    ranked: list[RankedDoc] = []
    for info in candidate_docs:
        try:
            raw = download_file(access_token, info.id)
        except Exception as exc:
            logger.warning("Skip doc %s (%s): %s", info.name, info.id, exc)
            continue

        preview = _doc_preview(raw, info.name, settings.drive_preview_chars)
        # Include the filename so similarly named memos still rank if text is sparse.
        embed_text = f"{info.name}\n{preview}"
        doc_vec = embeddings.embed([embed_text[: settings.drive_preview_chars]])[0]
        score = _cosine(query_vec, doc_vec)
        ranked.append(
            RankedDoc(
                info=info.model_copy(update={"score": score}),
                file_bytes=raw,
                preview_text=preview,
                score=score,
            )
        )

    ranked.sort(key=lambda r: r.score, reverse=True)
    selected = ranked[:max_docs]
    for item in selected:
        logger.info(
            "Selected Drive doc %s score=%.4f",
            item.info.name,
            item.score,
        )
    return selected
