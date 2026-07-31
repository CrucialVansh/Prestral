from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from app.config import Settings
from app.models.schemas import DriveFileInfo, StorageConnection
from app.services.doc_select import _cosine, rank_and_select_docs
from app.services.google_drive import classify_mime
from app.store import DriveConnectionRecord, GoogleTokens, connection_store


def test_classify_mime() -> None:
    assert classify_mime(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ) == "slides"
    assert classify_mime(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) == "doc"
    assert classify_mime("application/pdf") == "doc"
    assert classify_mime("image/png") == "other"


def test_cosine_identical() -> None:
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine(v, v) - 1.0) < 1e-6


def test_google_auth_url_requires_config(client, monkeypatch) -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    get_settings.cache_clear()

    res = client.get("/api/storage/google/auth-url")
    assert res.status_code == 503


def test_list_files_with_mock_connection(client) -> None:
    conn = StorageConnection(
        id="conn-1",
        provider="google_drive",
        email="user@example.com",
        created_at=datetime.now(UTC).isoformat(),
    )
    connection_store.put(
        DriveConnectionRecord(
            connection=conn,
            tokens=GoogleTokens(access_token="tok", refresh_token="ref"),
        )
    )

    fake_files = [
        {
            "id": "s1",
            "name": "deck.pptx",
            "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "modifiedTime": "2026-01-01T00:00:00.000Z",
        },
        {
            "id": "d1",
            "name": "notes.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "modifiedTime": "2026-01-02T00:00:00.000Z",
        },
        {
            "id": "d2",
            "name": "other.pdf",
            "mimeType": "application/pdf",
            "modifiedTime": "2026-01-03T00:00:00.000Z",
        },
    ]

    with patch("app.services.drive_import.list_drive_files", return_value=fake_files):
        res = client.get("/api/storage/files", params={"connection_id": "conn-1"})

    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["slides"]) == 1
    assert body["slides"][0]["name"] == "deck.pptx"
    assert len(body["docs"]) == 2


def test_rank_and_select_docs_picks_best(sample_pptx_bytes, sample_docx_bytes) -> None:
    settings = Settings(
        mistral_api_key="x",
        drive_preview_chars=2000,
        drive_max_auto_docs=1,
    )

    candidates = [
        DriveFileInfo(
            id="relevant",
            name="q3-financials.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            kind="doc",
        ),
        DriveFileInfo(
            id="irrelevant",
            name="recipes.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            kind="doc",
        ),
    ]

    def fake_download(token, file_id):
        return sample_docx_bytes

    class FakeEmbed:
        def __init__(self, _settings):
            pass

        def embed(self, texts):
            out = []
            for t in texts:
                lower = t.lower()
                if "recipes" in lower:
                    out.append([0.0, 1.0])
                elif "q3-financials" in lower:
                    out.append([0.95, 0.05])
                else:
                    out.append([1.0, 0.0])
            return out

    with (
        patch("app.services.doc_select.download_file", side_effect=fake_download),
        patch("app.services.doc_select.EmbeddingsClient", FakeEmbed),
    ):
        ranked = rank_and_select_docs(
            access_token="tok",
            slides_bytes=sample_pptx_bytes,
            candidate_docs=candidates,
            settings=settings,
            max_docs=1,
        )

    assert len(ranked) == 1
    assert ranked[0].info.id == "relevant"
