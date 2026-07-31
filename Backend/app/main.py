"""Prestral FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.schemas import HealthResponse
from app.routers import decks, query, sessions, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# Fail fast if required config (e.g. MISTRAL_API_KEY) is missing.
get_settings()

API_DESCRIPTION = """
## Prestral API (frontend guide)

Build an interactive slide viewer where each shape is a **hotspot**:

1. **Ingest** a PPTX + supporting doc(s) via local upload **or** Google Drive
2. Render slides and overlay ``components[].bbox`` (normalized 0–1)
3. **Hover** → show precomputed ``context`` (no extra call)
4. **Click** → open a **session chat** for that ``component_id``
5. Optionally set **audience** (``swe``, ``marketing``, …) so answers match the reader

### Typical sequence

```
POST /api/decks/upload          → deck.id + slides[].components[]
POST /api/decks/{id}/sessions   → { component_id, audience }
POST .../sessions/{sid}/messages → multi-turn Q&A
```

Or with Drive: ``GET /api/storage/google/auth-url`` → files → ``POST /api/storage/import``.

### Important

- Storage is **in-memory** — restarting the server clears decks, sessions, and Drive connections.
- CORS is open for local frontend development.
- Interactive docs: this page (Swagger) or ``/redoc``.
"""

app = FastAPI(
    title="Prestral API",
    description=API_DESCRIPTION,
    version="0.1.0",
    openapi_tags=[
        {
            "name": "health",
            "description": "Liveness checks.",
        },
        {
            "name": "decks",
            "description": "Upload / list / fetch analyzed slide decks.",
        },
        {
            "name": "query",
            "description": "Single-shot ask / summarize / explain (no chat history).",
        },
        {
            "name": "sessions",
            "description": "Multi-turn chats scoped to a component (switchable sessions).",
        },
        {
            "name": "storage",
            "description": "Google Drive OAuth, file listing, and RAG-backed import.",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(decks.router)
app.include_router(query.router)
app.include_router(sessions.router)
app.include_router(storage.router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
)
async def health() -> HealthResponse:
    """Return ``{ \"status\": \"ok\" }`` when the API process is up."""
    return HealthResponse()
