from __future__ import annotations

from typing import Sequence

import numpy as np
from mistralai.client import Mistral

from app.config import Settings
from app.models.schemas import DocChunk


class EmbeddingsClient:
    def __init__(self, settings: Settings) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._model = settings.mistral_embed_model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        # Mistral embeddings API accepts a batch of inputs.
        vectors: list[list[float]] = []
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            res = self._client.embeddings.create(model=self._model, inputs=batch)
            # Sort by index to preserve order.
            ordered = sorted(res.data, key=lambda d: d.index)
            vectors.extend([list(d.embedding) for d in ordered])
        return vectors

    def embed_chunks(self, chunks: list[DocChunk]) -> list[DocChunk]:
        texts = [c.text for c in chunks]
        vectors = self.embed(texts)
        for chunk, vec in zip(chunks, vectors):
            chunk.embedding = vec
        return chunks


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between vector a and rows of matrix b."""
    a_norm = a / (np.linalg.norm(a) + 1e-12)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
    return b_norm @ a_norm


def top_k_similar(
    query_vector: list[float],
    chunks: list[DocChunk],
    k: int = 4,
) -> list[DocChunk]:
    """Return the top-k DocChunks most similar to query_vector."""
    embedded = [c for c in chunks if c.embedding]
    if not embedded:
        return []

    matrix = np.array([c.embedding for c in embedded], dtype=np.float64)
    query = np.array(query_vector, dtype=np.float64)
    scores = cosine_similarity(query, matrix)
    k = min(k, len(embedded))
    top_idx = np.argsort(scores)[::-1][:k]
    return [embedded[int(i)] for i in top_idx]
