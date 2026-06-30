"""Agentic RAG chat service (ported from case-assistant-agent).

Orchestrates a single ``/chat/query`` request: UUID validation, the inbound PII guard,
conversation-history loading, workflow execution, optional answer redaction, persistence of the
user + assistant turns, and assembly of the ``QueryResponse`` contract. It also exposes the
conversation-management operations (history, list/get/delete sessions, clear history).

The MAF ``WorkflowBuilder`` from case-assistant-agent is replaced by ``AgenticRAGWorkflow`` —
a plain async loop that drives Casewright's synchronous Azure clients directly.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from casewright.agentic.models import AgenticRAGState, _utcnow
from casewright.agentic.pii import PIIDetectionService
from casewright.agentic.schemas import ChatHistoryMessage, QueryResponse
from casewright.agentic.workflow import AgenticRAGWorkflow
from casewright.core.settings import get_settings
from casewright.repositories.chat_history import ChatHistoryRepository

logger = logging.getLogger(__name__)

_PII_REFUSAL_TEMPLATE = (
    "I'm unable to process this request because it appears to contain personal or sensitive "
    "information ({categories}). Please remove any personal data and try again."
)


class ChatService:
    """Single entry point for the agentic RAG chat experience."""

    def __init__(self) -> None:
        self._history = ChatHistoryRepository()
        self._pii_service: PIIDetectionService | None = None

    @property
    def pii_service(self) -> PIIDetectionService:
        if self._pii_service is None:
            self._pii_service = PIIDetectionService()
        return self._pii_service

    # ------------------------------------------------------------------ PII guard

    def _check_prompt_for_pii(
        self, query: str, session_id: str, user_id: str | None
    ) -> QueryResponse | None:
        """Return a refusal ``QueryResponse`` when the prompt must be blocked, else ``None``."""
        s = get_settings()
        if not s.pii_active:
            return None

        try:
            result = self.pii_service.detect_pii(query)
        except Exception as exc:  # noqa: BLE001 - fail open so a misconfig doesn't take chat down
            logger.error("PII scan failed, proceeding without guard: %s", exc)
            return None

        if not result.contains_pii:
            return None

        categories = sorted({e.category for e in result.entities})
        logger.warning(
            "[PII Guard] Detected %d entities in prompt (session=%s, user=%s): %s",
            len(result.entities),
            session_id,
            user_id,
            categories,
        )

        if not (s.pii_block_on_detection or s.pii_mode == "block"):
            return None

        return QueryResponse(
            answer=_PII_REFUSAL_TEMPLATE.format(categories=", ".join(categories)),
            citations=[],
            document_count=0,
            session_id=session_id,
            thought_process=[
                {
                    "step": "pii_guard",
                    "attempt": 0,
                    "details": {
                        "blocked": True,
                        "entity_count": len(result.entities),
                        "categories": categories,
                    },
                }
            ],
            search_history=[],
            decisions=["pii_blocked"],
            attempts=0,
        )

    # ------------------------------------------------------------------ public API

    async def query_async(
        self,
        query: str,
        session_id: str,
        user_id: str | None = None,
        chat_history: list[ChatHistoryMessage] | None = None,
        filters: Any | None = None,
    ) -> QueryResponse:
        """Execute an agentic RAG query and return the full ``QueryResponse``."""
        try:
            uuid.UUID(session_id)
        except (ValueError, AttributeError, TypeError) as e:
            raise ValueError(
                f"Invalid session_id format. Must be a valid UUID. Error: {e}"
            ) from e

        s = get_settings()
        logger.info("Executing agentic RAG query: %s...", query[:100])

        # Inbound PII guard — short-circuits before any retrieval / LLM call.
        pii_response = self._check_prompt_for_pii(query, session_id, user_id)
        if pii_response is not None:
            if user_id:
                try:
                    self._history.append_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="user",
                        content="[redacted: user prompt blocked by PII guard]",
                    )
                    self._history.append_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="assistant",
                        content=pii_response.answer,
                        metadata={"pii_blocked": True},
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error("Failed to persist PII-blocked turn: %s", e)
            return pii_response

        # Load conversation history (Cosmos) or fall back to the request payload.
        chat_history_dict: list[dict[str, str]] = []
        if user_id:
            try:
                stored = self._history.get_user_chat_history(
                    session_id=session_id,
                    user_id=user_id,
                    max_messages=s.workflow_chat_history_window,
                )
                chat_history_dict = [
                    {"role": m["role"], "content": m["content"]} for m in stored
                ]
                logger.info("Loaded %d messages from chat history", len(chat_history_dict))
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load chat history: %s", e)

        if not chat_history_dict and chat_history:
            chat_history_dict = [
                {"role": msg.role.value, "content": msg.content} for msg in chat_history
            ]

        filters_dict = None
        if filters is not None:
            filters_dict = (
                filters.model_dump(exclude_none=True)
                if hasattr(filters, "model_dump")
                else filters
            )

        state = AgenticRAGState(
            query=query,
            user_id=user_id,
            session_id=session_id,
            chat_history=chat_history_dict,
            filters=filters_dict,
            max_attempts=s.workflow_max_retrieval_iterations,
        )

        workflow = AgenticRAGWorkflow()
        final_state = await workflow.run(state)

        answer_text = final_state.answer or "Unable to generate answer"

        # Persist the user + assistant turns.
        if user_id:
            try:
                self._history.append_message(
                    user_id=user_id, session_id=session_id, role="user", content=query
                )
                self._history.append_message(
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content=answer_text,
                    metadata={
                        "citations": [c.model_dump() for c in (final_state.citations or [])],
                        "document_count": len(final_state.vetted_results or []),
                    },
                )
                logger.info("Saved conversation to Cosmos DB: %s", session_id)
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to save conversation: %s", e)

        return self._build_response(session_id, final_state)

    def _build_response(self, session_id: str, final_state: AgenticRAGState) -> QueryResponse:
        response = QueryResponse(
            answer=final_state.answer or "",
            citations=final_state.citations or [],
            document_count=len(final_state.vetted_results or []),
            session_id=session_id,
            thought_process=final_state.thought_process or [],
            search_history=final_state.search_history or [],
            decisions=final_state.decisions or [],
            attempts=final_state.current_attempt,
            timestamp=_utcnow(),
        )
        logger.info(
            "Query completed: %d chars, %d citations",
            len(response.answer),
            len(response.citations),
        )
        return response

    # ------------------------------------------------------------------ conversation management

    async def get_user_chat_history(
        self, session_id: str, user_id: str, max_messages: int | None = None
    ) -> list[dict[str, Any]]:
        return self._history.get_user_chat_history(
            session_id=session_id, user_id=user_id, max_messages=max_messages
        )

    async def list_user_chat_sessions(
        self, user_id: str, max_results: int = 100
    ) -> list[dict[str, Any]]:
        return self._history.list_user_chat_sessions(user_id=user_id, max_results=max_results)

    async def delete_user_chat_session(self, session_id: str, user_id: str) -> int:
        return self._history.delete_user_chat_session(session_id=session_id, user_id=user_id)

    async def clear_user_chat_history(self, user_id: str) -> int:
        return self._history.clear_user_chat_history(user_id=user_id)
