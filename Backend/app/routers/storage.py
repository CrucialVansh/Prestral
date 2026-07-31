"""Google Drive connect, browse, and import."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.models.schemas import (
    DeckAnalysisResponse,
    DriveFileListResponse,
    DriveImportRequest,
    GoogleAuthUrlResponse,
    StorageConnection,
)
from app.services.drive_import import (
    create_connection_from_code,
    import_deck_from_drive,
    list_connection_files,
)
from app.services.google_drive import build_auth_url, require_google_oauth_config
from app.store import connection_store, deck_store

router = APIRouter(prefix="/api/storage", tags=["storage"])


def _deck_response(deck, selected_docs=None) -> DeckAnalysisResponse:
    return DeckAnalysisResponse(
        id=deck.id,
        slides_filename=deck.slides_filename,
        doc_filename=deck.doc_filename,
        doc_filenames=deck.doc_filenames or (
            [deck.doc_filename] if deck.doc_filename else []
        ),
        slides=deck.slides,
        source=deck.source,
        selected_docs=selected_docs or [],
    )


@router.get(
    "/google/auth-url",
    response_model=GoogleAuthUrlResponse,
    summary="Start Google Drive OAuth",
    response_description="Open ``auth_url`` in a browser / popup to authorize Drive.",
    responses={503: {"description": "GOOGLE_CLIENT_ID / SECRET not configured."}},
)
async def google_auth_url() -> GoogleAuthUrlResponse:
    """
    Begin Google Drive OAuth (readonly Drive scope).

    Frontend: open ``auth_url`` (popup or redirect). After consent, Google hits
    ``GET /api/storage/google/callback``, which shows a ``connection_id`` to copy
    or that you can parse if you control the redirect page.
    """
    settings = get_settings()
    require_google_oauth_config(settings)
    state = str(uuid4())
    connection_store.put_state(state)
    url = build_auth_url(settings=settings, state=state)
    return GoogleAuthUrlResponse(auth_url=url, state=state)


@router.get(
    "/google/callback",
    summary="Google OAuth callback",
    response_class=HTMLResponse,
    responses={400: {"description": "Missing/invalid code or state."}},
    include_in_schema=True,
)
async def google_callback(
    code: str = Query("", description="Authorization code from Google."),
    state: str = Query("", description="Must match the state from auth-url."),
) -> HTMLResponse:
    """
    OAuth redirect target. Exchanges the code, stores tokens in memory, and returns
    a simple HTML page with the ``connection_id``.

    Not JSON — intended for browser redirect during connect.
    """
    settings = get_settings()
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if not connection_store.consume_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    try:
        connection = create_connection_from_code(code, settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {exc}") from exc

    html = f"""<!doctype html>
<html><head><title>Google Drive connected</title></head>
<body style="font-family: system-ui; max-width: 40rem; margin: 3rem auto;">
  <h1>Google Drive connected</h1>
  <p>Email: <strong>{connection.email or "unknown"}</strong></p>
  <p>Connection ID (use this in the API / frontend):</p>
  <pre id="connection-id" style="padding:1rem;background:#f4f4f4;border-radius:8px;">{connection.id}</pre>
  <p>You can close this window and return to the app.</p>
</body></html>"""
    return HTMLResponse(content=html)


@router.get(
    "/connections",
    response_model=list[StorageConnection],
    summary="List Drive connections",
)
async def list_connections() -> list[StorageConnection]:
    """List Google Drive connections currently held in memory."""
    return connection_store.list()


@router.delete(
    "/connections/{connection_id}",
    summary="Disconnect Google Drive",
    responses={404: {"description": "Unknown connection id."}},
)
async def delete_connection(
    connection_id: str = Path(..., description="Connection id to remove."),
) -> dict[str, bool]:
    """Drop a stored Drive connection (tokens discarded)."""
    ok = connection_store.delete(connection_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    return {"deleted": True}


@router.get(
    "/files",
    response_model=DriveFileListResponse,
    summary="List Drive PPTX and docs",
    responses={400: {"description": "Missing connection_id and access_token."}},
)
async def list_files(
    connection_id: str | None = Query(
        None,
        description="From OAuth callback. Provide this **or** ``access_token``.",
    ),
    access_token: str | None = Query(
        None,
        description="Short-lived Google token if the frontend handled OAuth.",
    ),
    folder_id: str | None = Query(
        None,
        description="Optional Drive folder id to limit results.",
    ),
) -> DriveFileListResponse:
    """
    List importable files: ``slides`` (PPTX) and ``docs`` (DOCX/PDF).

    Show ``slides`` in a deck picker; ``docs`` are optional if you rely on
    ``auto_select_docs`` during import.
    """
    if not connection_id and not access_token:
        raise HTTPException(status_code=400, detail="Provide connection_id or access_token")
    conn_key, slides, docs = list_connection_files(
        connection_id=connection_id,
        access_token=access_token,
        folder_id=folder_id,
    )
    return DriveFileListResponse(connection_id=conn_key, slides=slides, docs=docs)


@router.post(
    "/import",
    response_model=DeckAnalysisResponse,
    summary="Import PPTX from Drive (+ RAG docs)",
    response_description="Same analysis shape as local upload, plus ``selected_docs``.",
    responses={
        400: {"description": "Bad request / no docs found / wrong file type."},
        500: {"description": "Download or analysis pipeline failed."},
    },
)
async def import_from_drive(body: DriveImportRequest) -> DeckAnalysisResponse:
    """
    Import a PPTX from Google Drive and run the full analysis pipeline.

    With ``auto_select_docs: true`` (default), the backend ranks available Drive
    docs against the slide text and grounds the deck in the top matches.

    With ``auto_select_docs: false``, pass explicit ``doc_file_ids``.

    Response matches local upload, and includes ``selected_docs`` so the UI can
    show which documents were used.
    """
    if not body.connection_id and not body.access_token:
        raise HTTPException(status_code=400, detail="Provide connection_id or access_token")

    settings = get_settings()
    try:
        deck, selected = import_deck_from_drive(body, settings)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Drive import failed: {exc}") from exc

    deck_store.put(deck)
    return _deck_response(deck, selected_docs=selected)
