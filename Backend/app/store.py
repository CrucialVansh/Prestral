from __future__ import annotations

import threading
from typing import Optional

from app.models.schemas import Deck, DeckSummary


class DeckStore:
    """Thread-safe in-memory store for processed decks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._decks: dict[str, Deck] = {}

    def put(self, deck: Deck) -> None:
        with self._lock:
            self._decks[deck.id] = deck

    def get(self, deck_id: str) -> Optional[Deck]:
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
                )
                for d in self._decks.values()
            ]

    def delete(self, deck_id: str) -> bool:
        with self._lock:
            if deck_id in self._decks:
                del self._decks[deck_id]
                return True
            return False


deck_store = DeckStore()
