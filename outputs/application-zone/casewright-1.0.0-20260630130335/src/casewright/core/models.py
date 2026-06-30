"""Pydantic models shared across the API surface."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Citation(BaseModel):
    document_title: str
    source_path: str
    score: float


class ChatRequest(BaseModel):
    message: str
    conversation_id: str
    tenant_id: str = "default"
    user_id: str = "anonymous"


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    runtime: Literal["foundry", "local"] = "local"


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime = Field(default_factory=_utcnow)


class IndexerStatus(BaseModel):
    indexer_name: str
    status: str
    last_run: datetime | None = None
    items_processed: int = 0
    items_failed: int = 0


FileChange = Literal["added", "updated", "unchanged", "deleted"]


class SyncFileResult(BaseModel):
    name: str
    change: FileChange


class SyncResult(BaseModel):
    site_id: str
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    indexer_triggered: bool = False

    @property
    def net_changes(self) -> int:
        return self.added + self.updated + self.deleted


class SyncRequest(BaseModel):
    tenant_id: str
    site_id: str
    requested_at: datetime = Field(default_factory=_utcnow)
