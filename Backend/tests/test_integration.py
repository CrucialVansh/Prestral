"""Live integration tests against the Mistral API (requires Backend/.env)."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


def test_upload_and_query_roundtrip(
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

    assert data["id"]
    assert data["slides_filename"] == "deck.pptx"
    assert data["doc_filename"] == "notes.docx"
    assert len(data["slides"]) == 2

    slide0 = data["slides"][0]
    assert slide0["components"], "expected at least one component on slide 0"

    # At least one component should have LLM-linked context from the doc
    contexts = [c.get("context", "") for c in slide0["components"]]
    assert any(ctx.strip() for ctx in contexts), (
        "expected Mistral to attach context to at least one component; "
        f"got contexts={contexts!r}"
    )

    for comp in slide0["components"]:
        bbox = comp["bbox"]
        for key in ("left", "top", "width", "height"):
            assert 0.0 <= bbox[key] <= 1.0

    deck_id = data["id"]

    listed = client.get("/api/decks")
    assert listed.status_code == 200
    assert any(d["id"] == deck_id for d in listed.json())

    fetched = client.get(f"/api/decks/{deck_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == deck_id

    component_id = slide0["components"][0]["id"]

    ask = client.post(
        f"/api/decks/{deck_id}/query",
        json={
            "mode": "ask",
            "question": "What drove the revenue growth in Q3?",
            "component_id": component_id,
        },
    )
    assert ask.status_code == 200, ask.text
    ask_body = ask.json()
    assert ask_body["mode"] == "ask"
    assert ask_body["answer"].strip()
    assert isinstance(ask_body["sources"], list)
    # Answer should reference growth / enterprise / revenue in some form
    answer_l = ask_body["answer"].lower()
    assert any(
        term in answer_l for term in ("revenue", "enterprise", "12%", "growth", "upsell")
    ), ask_body["answer"]

    summary = client.post(
        f"/api/decks/{deck_id}/query",
        json={"mode": "summarize", "slide_index": 0},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["answer"].strip()

    explain = client.post(
        f"/api/decks/{deck_id}/query",
        json={"mode": "explain", "component_id": component_id},
    )
    assert explain.status_code == 200, explain.text
    assert explain.json()["answer"].strip()
