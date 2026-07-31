from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.config import Settings

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

# PPTX / DOCX / PDF
SLIDES_MIME = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
DOC_MIME = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
}
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly openid email profile"


def require_google_oauth_config(settings: Settings) -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google Drive is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in Backend/.env"
            ),
        )


def build_auth_url(*, settings: Settings, state: str) -> str:
    require_google_oauth_config(settings)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": DRIVE_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, settings: Settings) -> dict[str, Any]:
    require_google_oauth_config(settings)
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30.0) as client:
        res = client.post(GOOGLE_TOKEN_URL, data=data)
        if res.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"Google token exchange failed: {res.text}",
            )
        return res.json()


def refresh_access_token(refresh_token: str, settings: Settings) -> dict[str, Any]:
    require_google_oauth_config(settings)
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=30.0) as client:
        res = client.post(GOOGLE_TOKEN_URL, data=data)
        if res.status_code >= 400:
            raise HTTPException(
                status_code=401,
                detail=f"Google token refresh failed: {res.text}",
            )
        return res.json()


def fetch_user_email(access_token: str) -> str | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=20.0) as client:
        res = client.get(GOOGLE_USERINFO_URL, headers=headers)
        if res.status_code >= 400:
            return None
        return res.json().get("email")


def _auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def list_drive_files(
    access_token: str,
    *,
    folder_id: str | None = None,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """List PPTX / DOCX / PDF files the user can access."""
    mime_filter = " or ".join(
        f"mimeType='{m}'" for m in sorted(SLIDES_MIME | DOC_MIME)
    )
    clauses = [f"({mime_filter})", "trashed=false"]
    if folder_id:
        clauses.append(f"'{folder_id}' in parents")
    query = " and ".join(clauses)

    params: dict[str, Any] = {
        "q": query,
        "pageSize": page_size,
        "fields": "files(id,name,mimeType,modifiedTime),nextPageToken",
        "orderBy": "modifiedTime desc",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }

    files: list[dict[str, Any]] = []
    with httpx.Client(timeout=60.0) as client:
        while True:
            res = client.get(
                DRIVE_FILES_URL,
                headers=_auth_header(access_token),
                params=params,
            )
            if res.status_code >= 400:
                raise HTTPException(
                    status_code=res.status_code,
                    detail=f"Drive list failed: {res.text}",
                )
            payload = res.json()
            files.extend(payload.get("files") or [])
            token = payload.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token

    return files


def download_file(access_token: str, file_id: str) -> bytes:
    with httpx.Client(timeout=120.0) as client:
        res = client.get(
            f"{DRIVE_FILES_URL}/{file_id}",
            headers=_auth_header(access_token),
            params={"alt": "media", "supportsAllDrives": "true"},
        )
        if res.status_code >= 400:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Drive download failed for {file_id}: {res.text}",
            )
        return res.content


def get_file_metadata(access_token: str, file_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        res = client.get(
            f"{DRIVE_FILES_URL}/{file_id}",
            headers=_auth_header(access_token),
            params={
                "fields": "id,name,mimeType,modifiedTime",
                "supportsAllDrives": "true",
            },
        )
        if res.status_code >= 400:
            raise HTTPException(
                status_code=res.status_code,
                detail=f"Drive metadata failed for {file_id}: {res.text}",
            )
        return res.json()


def classify_mime(mime_type: str) -> str:
    if mime_type in SLIDES_MIME:
        return "slides"
    if mime_type in DOC_MIME:
        return "doc"
    return "other"
