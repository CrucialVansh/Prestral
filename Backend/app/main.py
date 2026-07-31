"""Prestral FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models.schemas import HealthResponse
from app.routers import decks, query, sessions, storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

settings = get_settings()

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
- In production the built SPA is served from this same process (see ``STATIC_DIR``).
- Interactive docs: ``/docs`` or ``/redoc``.
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
    allow_credentials=False,
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


def _resolve_static_dir() -> Path | None:
    raw = os.environ.get("STATIC_DIR") or settings.static_dir
    if not raw:
        return None
    path = Path(raw)
    if path.is_dir() and (path / "index.html").is_file():
        return path
    return None


_static_dir = _resolve_static_dir()
if _static_dir is not None:
    assets = _static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    mock = _static_dir / "mock"
    if mock.is_dir():
        app.mount("/mock", StaticFiles(directory=mock), name="mock")

    @app.get("/")
    async def spa_index() -> FileResponse:
        return FileResponse(_static_dir / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        """Serve SPA for client-side routes; never shadow ``/api`` or ``/health``."""
        candidate = _static_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")
