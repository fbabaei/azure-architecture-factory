"""API request/response schemas for the agentic RAG chat endpoint.

Mirrors the case-assistant-agent ``/chat/query`` contract exactly so existing clients
(and the simple-chat SPA) work unchanged against Casewright.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from casewright.agentic.models import Citation


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatHistoryMessage(BaseModel):
    """Message in conversation history for the agentic RAG workflow."""

    role: MessageRole = Field(..., description="Role of the message sender")
    content: str = Field(..., min_length=1, description="Message content")


class SearchFilters(BaseModel):
    """Optional search filters for narrowing results."""

    date_from: str | None = Field(default=None, description="Filter docs modified on/after this date (ISO 8601)")
    date_to: str | None = Field(default=None, description="Filter docs modified on/before this date (ISO 8601)")
    document_type: str | None = Field(default=None, description="Filter by content/document type")
    category: str | None = Field(default=None, description="Filter by document category (index permitting)")
    custom: str | None = Field(default=None, description="Raw OData filter expression appended to the generated filter")


class QueryRequest(BaseModel):
    """Request payload for the agentic RAG query endpoint."""

    query: str = Field(..., min_length=1, max_length=2000, description="The user's question or query")
    session_id: str = Field(..., description="Session ID (must be a valid UUID) for conversation context")
    user_id: str | None = Field(default=None, description="Optional user identifier")
    chat_history: list[ChatHistoryMessage] | None = Field(default=None, description="Previous conversation messages")
    filters: SearchFilters | None = Field(default=None, description="Optional filters to narrow search results")
    stream: bool = Field(default=False, description="Enable streaming response (not yet implemented)")


class QueryResponse(BaseModel):
    """Response payload for the agentic RAG query endpoint."""

    answer: str = Field(..., description="The generated answer text")
    citations: list[Citation] = Field(default_factory=list, description="Citations with document metadata")
    document_count: int = Field(default=0, description="Number of documents retrieved")
    session_id: str | None = Field(default=None, description="Session ID for this conversation")
    thought_process: list[dict[str, Any]] = Field(default_factory=list, description="Step-by-step execution log")
    search_history: list[dict[str, Any]] = Field(default_factory=list, description="History of search attempts")
    decisions: list[str] = Field(default_factory=list, description="Reflection-agent decisions per iteration")
    attempts: int = Field(default=0, description="Number of search attempts made")
    timestamp: datetime = Field(default_factory=_utcnow, description="Response generation timestamp")
