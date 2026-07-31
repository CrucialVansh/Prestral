from __future__ import annotations

import threading
from dataclasses import dataclass

from app.models.schemas import (
    ChatSession,
    ChatSessionSummary,
    Deck,
    DeckSummary,
    StorageConnection,
)


@dataclass
class GoogleTokens:
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None
    email: str | None = None


@dataclass
class DriveConnectionRecord:
    connection: StorageConnection
    tokens: GoogleTokens


class DeckStore:
    """Thread-safe in-memory store for processed decks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._decks: dict[str, Deck] = {}

    def put(self, deck: Deck) -> None:
        with self._lock:
            self._decks[deck.id] = deck

    def get(self, deck_id: str) -> Deck | None:
        with self._lock:
            return self._decks.get(deck_id)

    def list(self) -> list[DeckSummary]:
        with self._lock:
            return [
                DeckSummary(
                    id=d.id,
                    slides_filename=d.slides_filename,
                    doc_filename=d.doc_filename,
                    slide_count=len(d.slides),
                    source=d.source,
                )
                for d in self._decks.values()
            ]

    def delete(self, deck_id: str) -> bool:
        with self._lock:
            if deck_id in self._decks:
                del self._decks[deck_id]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._decks.clear()


class SessionStore:
    """
    In-memory chat sessions.

    Primary key: session_id.
    Also indexes (deck_id, component_id) -> session_id for get-or-create,
    so reopening the same hotspot resumes the same conversation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, ChatSession] = {}
        self._by_component: dict[tuple[str, str], str] = {}

    def put(self, session: ChatSession, *, index_component: bool = True) -> None:
        with self._lock:
            self._sessions[session.id] = session
            if index_component:
                self._by_component[(session.deck_id, session.component_id)] = session.id

    def get(self, session_id: str) -> ChatSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_by_component(self, deck_id: str, component_id: str) -> ChatSession | None:
        with self._lock:
            sid = self._by_component.get((deck_id, component_id))
            if sid is None:
                return None
            return self._sessions.get(sid)

    def list_for_deck(self, deck_id: str) -> list[ChatSessionSummary]:
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.deck_id == deck_id]
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            return [
                ChatSessionSummary(
                    id=s.id,
                    deck_id=s.deck_id,
                    component_id=s.component_id,
                    slide_index=s.slide_index,
                    title=s.title,
                    audience=s.audience,
                    message_count=len(s.messages),
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in sessions
            ]

    def delete(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return False
            key = (session.deck_id, session.component_id)
            if self._by_component.get(key) == session_id:
                del self._by_component[key]
            return True

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._by_component.clear()


class ConnectionStore:
    """In-memory Google Drive OAuth connections."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[str, DriveConnectionRecord] = {}
        self._oauth_states: dict[str, bool] = {}

    def put_state(self, state: str) -> None:
        with self._lock:
            self._oauth_states[state] = True

    def consume_state(self, state: str) -> bool:
        with self._lock:
            return self._oauth_states.pop(state, False)

    def put(self, record: DriveConnectionRecord) -> None:
        with self._lock:
            self._connections[record.connection.id] = record

    def get(self, connection_id: str) -> DriveConnectionRecord | None:
        with self._lock:
            return self._connections.get(connection_id)

    def list(self) -> list[StorageConnection]:
        with self._lock:
            return [r.connection for r in self._connections.values()]

    def delete(self, connection_id: str) -> bool:
        with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
                return True
            return False

    def update_tokens(self, connection_id: str, tokens: GoogleTokens) -> None:
        with self._lock:
            record = self._connections.get(connection_id)
            if record is None:
                return
            record.tokens = tokens

    def clear(self) -> None:
        with self._lock:
            self._connections.clear()
            self._oauth_states.clear()


deck_store = DeckStore()
session_store = SessionStore()
connection_store = ConnectionStore()
