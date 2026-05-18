"""Domain models for the extraction + clarification workload."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Clarification(BaseModel):
    field: str = Field(description="Mandatory field name that is still missing.")
    prompt: str = Field(description="Human-facing question that will elicit the value.")


class ExtractionDraft(BaseModel):
    document_id: str
    source_filename: str
    fields: dict[str, Any] = Field(default_factory=dict)
    raw_excerpt: str = ""


class ExtractionResult(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    raw_excerpt: str = ""


class UploadResponse(BaseModel):
    document_id: str
    clarifications: list[Clarification]
    draft: ExtractionDraft


class ChatRequest(BaseModel):
    field: str | None = Field(default=None)
    answer: str = Field(min_length=1)


class ChatResponse(BaseModel):
    document_id: str
    draft: ExtractionDraft
    clarifications: list[Clarification]


class ClarificationBundle(BaseModel):
    document_id: str
    clarifications: list[Clarification]


class DraftResponse(BaseModel):
    document_id: str
    draft: ExtractionDraft
    finalized_at: str
