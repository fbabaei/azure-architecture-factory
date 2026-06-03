"""Agentic RAG chat router — case-assistant-agent ``/chat`` contract for Casewright.

Exposes the agentic query endpoint plus full conversation management. Mounted under ``/api`` so
the effective paths are ``/api/chat/query``, ``/api/chat/history/{session_id}``, and
``/api/chat/conversations/...``. These live alongside Casewright's legacy ``POST /api/chat``
endpoint without collision.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, status

from casewright.agentic.chat_service import ChatService
from casewright.agentic.schemas import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["agentic-chat"])


@lru_cache
def _get_chat_service() -> ChatService:
    return ChatService()


@router.post("/query", response_model=QueryResponse)
async def agentic_query(request: QueryRequest) -> QueryResponse:
    """Execute an agentic RAG query (HyDE → search → reflection → cited answer)."""
    try:
        response = await _get_chat_service().query_async(
            query=request.query,
            session_id=request.session_id,
            user_id=request.user_id,
            chat_history=request.chat_history,
            filters=request.filters,
        )
        logger.info(
            "Agentic query completed: %d chars, %d citations",
            len(response.answer),
            len(response.citations),
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.error("Agentic query failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {e}",
        ) from e


@router.get("/history/{session_id}")
async def get_conversation_history(
    session_id: str, user_id: str, max_messages: int | None = None
) -> dict[str, Any]:
    """Return all messages for a session in chronological order."""
    try:
        messages = await _get_chat_service().get_user_chat_history(
            session_id, user_id, max_messages
        )
        return {
            "session_id": session_id,
            "user_id": user_id,
            "message_count": len(messages),
            "messages": messages,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to retrieve conversation history: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conversation history: {e}",
        ) from e


@router.get("/conversations/{user_id}")
async def list_user_conversations(user_id: str, max_results: int = 100) -> dict[str, Any]:
    """List all conversation sessions for a user."""
    try:
        sessions = await _get_chat_service().list_user_chat_sessions(user_id, max_results)
        return {"user_id": user_id, "session_count": len(sessions), "sessions": sessions}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to list conversations: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conversations: {e}",
        ) from e


@router.get("/conversations/{user_id}/{session_id}")
async def get_conversation(user_id: str, session_id: str) -> dict[str, Any]:
    """Retrieve a specific conversation thread."""
    try:
        thread = await _get_chat_service().get_user_chat_history(session_id, user_id)
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation not found: {session_id}",
            )
        return {"session_id": session_id, "user_id": user_id, "messages": thread}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to retrieve conversation: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conversation: {e}",
        ) from e


@router.delete("/conversations/{user_id}/{session_id}")
async def delete_conversation(user_id: str, session_id: str) -> dict[str, str]:
    """Delete a specific conversation thread."""
    try:
        await _get_chat_service().delete_user_chat_session(session_id, user_id)
        return {"status": "deleted", "session_id": session_id, "user_id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to delete conversation: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {e}",
        ) from e


@router.delete("/conversations/{user_id}")
async def clear_user_history(user_id: str) -> dict[str, Any]:
    """Delete all conversation threads for a user."""
    try:
        count = await _get_chat_service().clear_user_chat_history(user_id)
        return {"status": "cleared", "user_id": user_id, "deleted_count": count}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to clear user history: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear user history: {e}",
        ) from e
