"""HTTP-level API tests that do not require Mistral (error paths + session wiring)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.schemas import (
    BBox,
    Component,
    ComponentType,
    Deck,
    Slide,
    StorageConnection,
)
from app.store import DriveConnectionRecord, GoogleTokens, connection_store, deck_store


def _seed_deck() -> Deck:
    deck = Deck(
        id="deck-api",
        slides_filename="a.pptx",
        doc_filename="a.docx",
        doc_filenames=["a.docx"],
        source="upload",
        slides=[
            Slide(
                index=0,
                components=[
                    Component(
                        id="slide0-shape0",
                        type=ComponentType.TITLE,
                        bbox=BBox(left=0.1, top=0.1, width=0.8, height=0.2),
                        text="Title",
                        context="Context blurb",
                    )
                ],
            )
        ],
        doc_chunks=[],
    )
    deck_store.put(deck)
    return deck


def test_get_deck_404(client) -> None:
    res = client.get("/api/decks/does-not-exist")
    assert res.status_code == 404


def test_list_and_get_deck(client) -> None:
    deck = _seed_deck()
    listed = client.get("/api/decks")
    assert listed.status_code == 200
    assert any(d["id"] == deck.id for d in listed.json())

    got = client.get(f"/api/decks/{deck.id}")
    assert got.status_code == 200
    body = got.json()
    assert body["id"] == deck.id
    assert body["slides"][0]["components"][0]["bbox"]["left"] == 0.1
    assert "doc_filenames" in body


def test_query_deck_404(client) -> None:
    res = client.post(
        "/api/decks/missing/query",
        json={"mode": "ask", "question": "hi"},
    )
    assert res.status_code == 404


def test_session_delete_and_404(client) -> None:
    deck = _seed_deck()
    created = client.post(
        f"/api/decks/{deck.id}/sessions",
        json={"component_id": "slide0-shape0", "audience": "general"},
    )
    assert created.status_code == 200
    sid = created.json()["id"]

    deleted = client.delete(f"/api/decks/{deck.id}/sessions/{sid}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/api/decks/{deck.id}/sessions/{sid}")
    assert missing.status_code == 404


def test_session_unknown_component(client) -> None:
    deck = _seed_deck()
    res = client.post(
        f"/api/decks/{deck.id}/sessions",
        json={"component_id": "nope"},
    )
    assert res.status_code == 404


def test_storage_files_requires_auth(client) -> None:
    res = client.get("/api/storage/files")
    assert res.status_code == 400


def test_storage_import_requires_auth(client) -> None:
    res = client.post(
        "/api/storage/import",
        json={"slides_file_id": "abc", "auto_select_docs": True},
    )
    assert res.status_code == 400


def test_storage_delete_connection(client) -> None:
    conn = StorageConnection(
        id="c-del",
        provider="google_drive",
        email="a@b.com",
        created_at=datetime.now(UTC).isoformat(),
    )
    connection_store.put(
        DriveConnectionRecord(
            connection=conn,
            tokens=GoogleTokens(access_token="t"),
        )
    )
    res = client.delete("/api/storage/connections/c-del")
    assert res.status_code == 200
    assert client.delete("/api/storage/connections/c-del").status_code == 404


def test_storage_callback_invalid_state(client) -> None:
    res = client.get(
        "/api/storage/google/callback",
        params={"code": "x", "state": "bad"},
    )
    assert res.status_code == 400
