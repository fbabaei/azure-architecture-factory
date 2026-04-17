"""Pydantic models describing an MDR arrangement and agent payloads.

The MDR arrangement schema below is intentionally simplified to Phase 1
extraction fields. The canonical structure mirrors DAC6 / OECD MDR
reporting categories so downstream systems can map to existing
disclosure templates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Arrangement domain model
# ---------------------------------------------------------------------------


class PartyRole(str, Enum):
    intermediary = "intermediary"
    relevant_taxpayer = "relevant_taxpayer"
    associated_enterprise = "associated_enterprise"


class Party(BaseModel):
    role: PartyRole
    name: str | None = None
    tax_identification_number: str | None = None
    jurisdiction: str | None = Field(
        default=None, description="ISO 3166-1 alpha-2 country code"
    )
    address: str | None = None


class Hallmark(BaseModel):
    """A DAC6-style hallmark indicator supporting the arrangement."""

    code: str = Field(description="e.g. A1, B2, C1bi, D1, E3")
    category: Literal["A", "B", "C", "D", "E"]
    description: str | None = None


class MDRArrangement(BaseModel):
    arrangement_id: str | None = None
    reference: str | None = Field(
        default=None, description="Internal or client reference for the arrangement"
    )
    summary: str | None = None
    implementation_date: datetime | None = None
    value: float | None = Field(default=None, description="Transaction value")
    currency: str | None = Field(default=None, description="ISO 4217 currency code")
    main_benefit_test: bool | None = None
    hallmarks: list[Hallmark] = Field(default_factory=list)
    parties: list[Party] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)


# Mandatory fields that MUST be present before an arrangement draft can
# be produced. Missing values drive the clarification loop.
MANDATORY_FIELDS: tuple[str, ...] = (
    "reference",
    "summary",
    "implementation_date",
    "hallmarks",
    "parties",
    "jurisdictions",
)


# ---------------------------------------------------------------------------
# API payloads
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    arrangement_id: str
    blob_name: str
    content_type: str


class ExtractionResult(BaseModel):
    arrangement_id: str
    arrangement: MDRArrangement
    confidence: float = Field(ge=0.0, le=1.0)
    source_pages: int
    extraction_model: str


class ClarificationQuestion(BaseModel):
    field: str
    question: str
    hint: str | None = None


class ClarificationBundle(BaseModel):
    arrangement_id: str
    missing_fields: list[str]
    questions: list[ClarificationQuestion]
    is_complete: bool


class ChatTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ChatRequest(BaseModel):
    arrangement_id: str
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    arrangement_id: str
    reply: str
    arrangement: MDRArrangement
    clarifications: ClarificationBundle


class DraftResponse(BaseModel):
    arrangement_id: str
    arrangement: MDRArrangement
    is_complete: bool
    generated_at: datetime


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class QAResponse(BaseModel):
    question: str
    answer: str
    model: str


class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionSnapshot(BaseModel):
    session_id: str
    arrangement: MDRArrangement | None = None
    turns: list[ChatTurn] = Field(default_factory=list)


class SessionDeleteResponse(BaseModel):
    session_id: str
    deleted: bool


class ApiChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)


class ApiChatResponse(BaseModel):
    session_id: str
    mode: Literal["qa", "clarification", "off_topic"]
    reply: str
    arrangement: MDRArrangement | None = None
    clarifications: ClarificationBundle | None = None


class TextDraftRequest(BaseModel):
    session_id: str | None = None
    text: str = Field(min_length=20, max_length=120000)
    reference: str | None = None
