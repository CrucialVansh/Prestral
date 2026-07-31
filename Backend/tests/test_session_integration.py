"""Live multi-turn session chat against Mistral."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_session_multi_turn_chat(
    client, sample_pptx_bytes: bytes, sample_docx_bytes: bytes
) -> None:
    upload = client.post(
        "/api/decks/upload",
        files={
            "slides": (
                "deck.pptx",
                sample_pptx_bytes,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            "doc": (
                "notes.docx",
                sample_docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        },
    )
    assert upload.status_code == 200, upload.text
    data = upload.json()
    deck_id = data["id"]
    component_id = data["slides"][0]["components"][0]["id"]

    session = client.post(
        f"/api/decks/{deck_id}/sessions",
        json={"component_id": component_id},
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["id"]

    # Reopen same component -> same session
    again = client.post(
        f"/api/decks/{deck_id}/sessions",
        json={"component_id": component_id},
    )
    assert again.json()["id"] == session_id

    turn1 = client.post(
        f"/api/decks/{deck_id}/sessions/{session_id}/messages",
        json={
            "mode": "ask",
            "content": "What drove the revenue growth in Q3?",
        },
    )
    assert turn1.status_code == 200, turn1.text
    a1 = turn1.json()["assistant_message"]["content"].lower()
    assert any(t in a1 for t in ("revenue", "enterprise", "growth", "12%", "upsell"))

    turn2 = client.post(
        f"/api/decks/{deck_id}/sessions/{session_id}/messages",
        json={
            "mode": "ask",
            "content": "Based on what you just said, what should I emphasize in the pitch?",
        },
    )
    assert turn2.status_code == 200, turn2.text
    assert turn2.json()["assistant_message"]["content"].strip()

    fetched = client.get(f"/api/decks/{deck_id}/sessions/{session_id}")
    assert fetched.status_code == 200
    assert len(fetched.json()["messages"]) == 4  # 2 user + 2 assistant
