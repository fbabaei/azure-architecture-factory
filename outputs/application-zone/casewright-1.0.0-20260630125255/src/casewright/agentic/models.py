"""Domain models for the agentic RAG engine.

These mirror the case-assistant-agent contract so the ``/api/chat/query`` endpoint
returns an identical payload shape. The ``Citation`` here intentionally differs from
``casewright.core.models.Citation`` (which keeps the simpler title/path/score shape used
by the legacy ``/api/chat`` endpoint and the Foundry path).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Citation(BaseModel):
    """Source document citation with chunk-level metadata (case-assistant shape)."""

    document_id: str = Field(..., description="Unique identifier for the source document")
    content_id: str = Field(..., description="Unique identifier for the content chunk")
    content: str | None = Field(default=None, description="The actual text content of the cited chunk")
    document_title: str | None = Field(default=None, description="Title of the source document")
    page_number: int | None = Field(default=None, description="Page number where the content appears")


class RetrievedDocument(BaseModel):
    """Document retrieved from Azure AI Search with relevance scores and metadata."""

    document_id: str = Field(..., description="Unique identifier for the source document")
    content_id: str = Field(..., description="Unique identifier for the content chunk")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Text content of the retrieved chunk")
    source: str = Field(..., description="Source path or URL of the document")
    page_number: int | None = Field(default=None, description="Page number of the chunk")
    score: float = Field(..., description="Hybrid search relevance score")
    reranker_score: float | None = Field(default=None, description="Semantic reranker score (if enabled)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional document metadata")


class RewrittenQuery(BaseModel):
    """Structured output of the HyDE query-rewriting step."""

    hypothetical_passage: str = Field(
        ..., description="Hypothetical document passage representing expected answer content"
    )
    reasoning: str = Field(..., description="Explanation of the rewriting strategy chosen")


class GeneratedAnswer(BaseModel):
    """Answer produced by the answer generator with inline citations."""

    answer_text: str = Field(..., description="Generated answer text with inline [n] citation markers")
    citations: list[Citation] = Field(default_factory=list, description="Ordered list of cited sources")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional generation metadata")


class ReviewDecision(BaseModel):
    """LLM decision for reviewing search results."""

    thought_process: str = Field(..., description="Reasoning for the decision")
    valid_results: list[int] = Field(..., description="Indices of valid results in the current result set")
    invalid_results: list[int] = Field(..., description="Indices of invalid results in the current result set")
    decision: Literal["retry", "finalize"] = Field(..., description="Whether to retry retrieval or finalise")


class AgenticRAGState(BaseModel):
    """Mutable state threaded through search → reflection → answer generation cycles."""

    query: str
    user_id: str | None = None
    session_id: str | None = None
    chat_history: list[dict[str, str]] | None = Field(default_factory=list)
    filters: dict[str, Any] | None = None

    # Iteration control
    max_attempts: int = 3
    current_attempt: int = 0
    search_history: list[dict[str, Any]] = Field(default_factory=list)
    previous_reviews: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)

    # Results tracking
    current_results: list[RetrievedDocument] = Field(default_factory=list)
    vetted_results: list[RetrievedDocument] = Field(default_factory=list)
    discarded_results: list[RetrievedDocument] = Field(default_factory=list)
    processed_content_ids: set[str] = Field(default_factory=set)

    # Routing decision
    decision: Literal["search", "reflect", "finalize", "answer"] = "search"

    # Final output
    answer: str | None = None
    citations: list[Citation] | None = None

    # Step-by-step execution log
    thought_process: list[dict[str, Any]] = Field(default_factory=list)
