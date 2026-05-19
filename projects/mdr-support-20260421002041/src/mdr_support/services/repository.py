"""In-memory repository for ExtractionDrafts (swap for Cosmos / SQL)."""
from __future__ import annotations

from threading import Lock

from ..models import ExtractionDraft


class DraftRepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[str, ExtractionDraft] = {}

    def put(self, draft: ExtractionDraft) -> None:
        with self._lock:
            self._store[draft.document_id] = draft

    def get(self, document_id: str) -> ExtractionDraft | None:
        with self._lock:
            return self._store.get(document_id)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())
