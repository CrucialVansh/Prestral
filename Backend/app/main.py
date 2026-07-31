from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.schemas import HealthResponse
from app.routers import decks, query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# Fail fast if required config (e.g. MISTRAL_API_KEY) is missing.
get_settings()

app = FastAPI(
    title="Prestral API",
    description=(
        "Upload a PPTX slide deck and a supporting DOCX/PDF document. "
        "The API scans slide components, relates them to the document via Mistral, "
        "and exposes a Q&A endpoint for ask / summarize / explain."
    ),
    version="0.1.0",
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


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()
