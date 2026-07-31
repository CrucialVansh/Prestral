"""Unit tests for component-scoped chat sessions (no LLM required for store/API wiring)."""

from __future__ import annotations

from app.models.schemas import Component, ComponentType, BBox, Deck, Slide
from app.models.schemas import CreateSessionRequest
from app.services.chat import get_or_create_session
from app.store import deck_store, session_store


def _tiny_deck() -> Deck:
    return Deck(
        id="deck-test",
        slides_filename="a.pptx",
        doc_filename="a.docx",
        slides=[
            Slide(
                index=0,
                notes="",
                components=[
                    Component(
                        id="slide0-shape0",
                        type=ComponentType.TITLE,
                        bbox=BBox(left=0.1, top=0.1, width=0.8, height=0.2),
                        text="Revenue Overview",
                        context="Grew 12% YoY",
                    ),
                    Component(
                        id="slide0-shape1",
                        type=ComponentType.BODY,
                        bbox=BBox(left=0.1, top=0.3, width=0.8, height=0.5),
                        text="Enterprise drove growth",
                    ),
                ],
            )
        ],
        doc_chunks=[],
    )


def test_get_or_create_reuses_session_for_same_component() -> None:
    session_store.clear()
    deck = _tiny_deck()
    deck_store.put(deck)

    s1 = get_or_create_session(deck, CreateSessionRequest(component_id="slide0-shape0"))
    s2 = get_or_create_session(deck, CreateSessionRequest(component_id="slide0-shape0"))
    assert s1.id == s2.id
    assert s1.component_id == "slide0-shape0"


def test_different_components_get_different_sessions() -> None:
    session_store.clear()
    deck = _tiny_deck()
    deck_store.put(deck)

    a = get_or_create_session(deck, CreateSessionRequest(component_id="slide0-shape0"))
    b = get_or_create_session(deck, CreateSessionRequest(component_id="slide0-shape1"))
    assert a.id != b.id

    listed = session_store.list_for_deck(deck.id)
    assert {s.component_id for s in listed} == {"slide0-shape0", "slide0-shape1"}


def test_force_new_starts_fresh_session() -> None:
    session_store.clear()
    deck = _tiny_deck()
    deck_store.put(deck)

    first = get_or_create_session(deck, CreateSessionRequest(component_id="slide0-shape0"))
    second = get_or_create_session(
        deck, CreateSessionRequest(component_id="slide0-shape0", force_new=True)
    )
    assert first.id != second.id
    # Component index now points at the newest session
    assert session_store.get_by_component(deck.id, "slide0-shape0").id == second.id
    # Old session remains listable for switching back
    ids = {s.id for s in session_store.list_for_deck(deck.id)}
    assert first.id in ids and second.id in ids


def test_sessions_http_create_list_get(client) -> None:
    deck = _tiny_deck()
    deck_store.put(deck)

    created = client.post(
        f"/api/decks/{deck.id}/sessions",
        json={"component_id": "slide0-shape0"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["component_id"] == "slide0-shape0"
    assert body["messages"] == []

    again = client.post(
        f"/api/decks/{deck.id}/sessions",
        json={"component_id": "slide0-shape0"},
    )
    assert again.json()["id"] == body["id"]

    listed = client.get(f"/api/decks/{deck.id}/sessions")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/decks/{deck.id}/sessions/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]
