"""Session service: records chat turns per document."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass
class ChatTurn:
    at: str
    field: str
    answer: str


@dataclass
class Session:
    document_id: str
    turns: list[ChatTurn] = field(default_factory=list)


class SessionService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, Session] = {}

    def record_turn(self, document_id: str, field: str, answer: str) -> None:
        with self._lock:
            session = self._sessions.setdefault(document_id, Session(document_id=document_id))
            session.turns.append(ChatTurn(at=datetime.now(timezone.utc).isoformat(), field=field, answer=answer))

    def get(self, document_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(document_id)
