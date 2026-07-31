from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException

from app.config import Settings, get_settings
from app.models.schemas import (
    Deck,
    DriveFileInfo,
    DriveImportRequest,
    StorageConnection,
)
from app.services.analysis import analyze_deck_multi
from app.services.doc_select import rank_and_select_docs
from app.services.google_drive import (
    classify_mime,
    download_file,
    exchange_code_for_tokens,
    fetch_user_email,
    get_file_metadata,
    list_drive_files,
    refresh_access_token,
)
from app.store import (
    DriveConnectionRecord,
    GoogleTokens,
    connection_store,
)

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def create_connection_from_code(code: str, settings: Settings) -> StorageConnection:
    token_payload = exchange_code_for_tokens(code, settings)
    access = token_payload.get("access_token")
    if not access:
        raise HTTPException(status_code=400, detail="Google did not return an access_token")

    tokens = GoogleTokens(
        access_token=access,
        refresh_token=token_payload.get("refresh_token"),
        token_type=token_payload.get("token_type") or "Bearer",
        expires_in=token_payload.get("expires_in"),
        email=fetch_user_email(access),
    )
    connection = StorageConnection(
        id=str(uuid4()),
        provider="google_drive",
        email=tokens.email,
        created_at=_utc_now(),
    )
    connection_store.put(DriveConnectionRecord(connection=connection, tokens=tokens))
    return connection


def resolve_access_token(
    *,
    connection_id: str | None,
    access_token: str | None,
    settings: Settings,
) -> str:
    if access_token and access_token.strip():
        return access_token.strip()

    if not connection_id:
        raise HTTPException(
            status_code=400,
            detail="Provide connection_id or access_token",
        )

    record = connection_store.get(connection_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")

    # Prefer existing access token; refresh if we have a refresh_token and it fails later.
    return record.tokens.access_token


def refresh_connection_token(connection_id: str, settings: Settings) -> str:
    record = connection_store.get(connection_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
    if not record.tokens.refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Connection has no refresh_token; reconnect Google Drive",
        )
    payload = refresh_access_token(record.tokens.refresh_token, settings)
    access = payload.get("access_token")
    if not access:
        raise HTTPException(status_code=401, detail="Token refresh did not return access_token")
    record.tokens.access_token = access
    if payload.get("expires_in") is not None:
        record.tokens.expires_in = payload.get("expires_in")
    connection_store.update_tokens(connection_id, record.tokens)
    return access


def _to_file_info(raw: dict) -> DriveFileInfo:
    mime = raw.get("mimeType") or ""
    return DriveFileInfo(
        id=raw["id"],
        name=raw.get("name") or raw["id"],
        mime_type=mime,
        kind=classify_mime(mime),  # type: ignore[arg-type]
        modified_time=raw.get("modifiedTime"),
    )


def list_connection_files(
    *,
    connection_id: str | None = None,
    access_token: str | None = None,
    folder_id: str | None = None,
) -> tuple[str, list[DriveFileInfo], list[DriveFileInfo]]:
    settings = get_settings()
    token = resolve_access_token(
        connection_id=connection_id,
        access_token=access_token,
        settings=settings,
    )
    try:
        raw_files = list_drive_files(token, folder_id=folder_id)
    except HTTPException as exc:
        if exc.status_code in {401, 403} and connection_id:
            token = refresh_connection_token(connection_id, settings)
            raw_files = list_drive_files(token, folder_id=folder_id)
        else:
            raise

    slides: list[DriveFileInfo] = []
    docs: list[DriveFileInfo] = []
    for raw in raw_files:
        info = _to_file_info(raw)
        if info.kind == "slides":
            slides.append(info)
        elif info.kind == "doc":
            docs.append(info)

    return connection_id or "token", slides, docs


def import_deck_from_drive(body: DriveImportRequest, settings: Settings) -> tuple[Deck, list[DriveFileInfo]]:
    token = resolve_access_token(
        connection_id=body.connection_id,
        access_token=body.access_token,
        settings=settings,
    )

    def _download(file_id: str) -> tuple[bytes, dict]:
        try:
            meta = get_file_metadata(token, file_id)
            raw = download_file(token, file_id)
            return raw, meta
        except HTTPException as exc:
            if exc.status_code in {401, 403} and body.connection_id:
                refreshed = refresh_connection_token(body.connection_id, settings)
                meta = get_file_metadata(refreshed, file_id)
                raw = download_file(refreshed, file_id)
                return raw, meta
            raise

    slides_bytes, slides_meta = _download(body.slides_file_id)
    slides_name = slides_meta.get("name") or "slides.pptx"
    if classify_mime(slides_meta.get("mimeType") or "") != "slides":
        raise HTTPException(
            status_code=400,
            detail=f"Selected slides file must be a PPTX (got {slides_meta.get('mimeType')})",
        )

    selected_infos: list[DriveFileInfo] = []
    docs_payload: list[tuple[bytes, str]] = []

    if body.auto_select_docs:
        # Ensure we use a working token (refresh if needed via list helper).
        _, _, candidate_docs = list_connection_files(
            connection_id=body.connection_id,
            access_token=None if body.connection_id else token,
            folder_id=body.folder_id,
        )
        # list_connection_files may have refreshed the connection token
        token = resolve_access_token(
            connection_id=body.connection_id,
            access_token=None if body.connection_id else token,
            settings=settings,
        )

        max_docs = body.max_docs or settings.drive_max_auto_docs
        ranked = rank_and_select_docs(
            access_token=token,
            slides_bytes=slides_bytes,
            candidate_docs=candidate_docs,
            settings=settings,
            max_docs=max_docs,
        )
        if not ranked:
            raise HTTPException(
                status_code=400,
                detail="No relevant DOCX/PDF documents found in Drive to ground this deck",
            )
        for item in ranked:
            selected_infos.append(item.info)
            docs_payload.append((item.file_bytes, item.info.name))
    else:
        if not body.doc_file_ids:
            raise HTTPException(
                status_code=400,
                detail="doc_file_ids required when auto_select_docs is false",
            )
        for doc_id in body.doc_file_ids:
            raw, meta = _download(doc_id)
            info = _to_file_info(meta)
            if info.kind != "doc":
                raise HTTPException(
                    status_code=400,
                    detail=f"File {info.name} is not a DOCX/PDF document",
                )
            selected_infos.append(info)
            docs_payload.append((raw, info.name))

    deck = analyze_deck_multi(
        slides_bytes=slides_bytes,
        slides_filename=slides_name,
        docs=docs_payload,
        settings=settings,
        source="google_drive",
    )
    return deck, selected_infos
