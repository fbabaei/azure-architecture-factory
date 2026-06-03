"""Cosmos-backed chat history (hierarchical partition key tenantId/userId/conversationId).

Each turn is stored as its own item so appends are cheap and a conversation read is a single
partition query. All access uses AAD (DefaultAzureCredential) — no account keys.
"""
from __future__ import annotations

import logging
import uuid

from casewright.core.clients import get_cosmos_client
from casewright.core.models import ChatTurn
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)


class ChatHistoryRepository:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = get_cosmos_client()

    def _container(self):
        s = self._settings
        db = self._client.get_database_client(s.cosmos_database)
        return db.get_container_client(s.cosmos_history_container)

    async def get_turns(self, tenant_id: str, user_id: str, conversation_id: str) -> list[ChatTurn]:
        container = self._container()
        query = (
            "SELECT c.role, c.content, c.created_at FROM c "
            "WHERE c.conversationId = @cid ORDER BY c.created_at ASC"
        )
        items = container.query_items(
            query=query,
            parameters=[{"name": "@cid", "value": conversation_id}],
            partition_key=[tenant_id, user_id, conversation_id],
        )
        turns: list[ChatTurn] = []
        for item in items:
            turns.append(ChatTurn(role=item["role"], content=item["content"]))
        return turns

    async def append_turns(
        self, tenant_id: str, user_id: str, conversation_id: str, turns: list[ChatTurn]
    ) -> None:
        container = self._container()
        for turn in turns:
            container.upsert_item(
                {
                    "id": str(uuid.uuid4()),
                    "tenantId": tenant_id,
                    "userId": user_id,
                    "conversationId": conversation_id,
                    "role": turn.role,
                    "content": turn.content,
                    "created_at": turn.created_at.isoformat(),
                }
            )
        logger.info("appended %d turns to %s", len(turns), conversation_id)

    # ------------------------------------------------------------------
    # Agentic conversation API (case-assistant-agent parity).
    #
    # These methods address conversations by ``user_id`` / ``session_id`` (where
    # ``session_id`` maps onto ``conversationId``) and default the tenant partition to
    # ``"default"`` — matching the legacy ``/api/chat`` defaults. Messages may carry an
    # optional ``metadata`` payload (e.g. citations + document_count for assistant turns).
    # ------------------------------------------------------------------

    DEFAULT_TENANT = "default"

    def append_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        tenant_id: str | None = None,
    ) -> None:
        from datetime import datetime, timezone

        tenant = tenant_id or self.DEFAULT_TENANT
        container = self._container()
        item = {
            "id": str(uuid.uuid4()),
            "tenantId": tenant,
            "userId": user_id,
            "conversationId": session_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            item["metadata"] = metadata
        container.upsert_item(item)

    def get_user_chat_history(
        self,
        session_id: str,
        user_id: str,
        max_messages: int | None = None,
        tenant_id: str | None = None,
    ) -> list[dict]:
        tenant = tenant_id or self.DEFAULT_TENANT
        container = self._container()
        query = (
            "SELECT c.role, c.content, c.created_at, c.metadata FROM c "
            "WHERE c.conversationId = @cid ORDER BY c.created_at ASC"
        )
        items = list(
            container.query_items(
                query=query,
                parameters=[{"name": "@cid", "value": session_id}],
                partition_key=[tenant, user_id, session_id],
            )
        )
        if max_messages is not None and max_messages > 0:
            items = items[-max_messages:]
        return [
            {
                "role": item["role"],
                "content": item["content"],
                "created_at": item.get("created_at"),
                "metadata": item.get("metadata"),
            }
            for item in items
        ]

    def list_user_chat_sessions(
        self, user_id: str, max_results: int = 100, tenant_id: str | None = None
    ) -> list[dict]:
        tenant = tenant_id or self.DEFAULT_TENANT
        container = self._container()
        query = (
            "SELECT c.conversationId, c.content, c.role, c.created_at FROM c "
            "ORDER BY c.created_at ASC"
        )
        items = container.query_items(query=query, partition_key=[tenant, user_id])
        sessions: dict[str, dict] = {}
        for item in items:
            cid = item.get("conversationId")
            if not cid:
                continue
            entry = sessions.setdefault(
                cid,
                {
                    "session_id": cid,
                    "message_count": 0,
                    "first_message": None,
                    "last_updated": None,
                },
            )
            entry["message_count"] += 1
            if entry["first_message"] is None and item.get("role") == "user":
                entry["first_message"] = item.get("content")
            entry["last_updated"] = item.get("created_at")
        ordered = sorted(
            sessions.values(), key=lambda s: s.get("last_updated") or "", reverse=True
        )
        return ordered[:max_results]

    def delete_user_chat_session(
        self, session_id: str, user_id: str, tenant_id: str | None = None
    ) -> int:
        tenant = tenant_id or self.DEFAULT_TENANT
        container = self._container()
        items = list(
            container.query_items(
                query="SELECT c.id FROM c WHERE c.conversationId = @cid",
                parameters=[{"name": "@cid", "value": session_id}],
                partition_key=[tenant, user_id, session_id],
            )
        )
        for item in items:
            container.delete_item(item["id"], partition_key=[tenant, user_id, session_id])
        logger.info("deleted %d messages from session %s", len(items), session_id)
        return len(items)

    def clear_user_chat_history(self, user_id: str, tenant_id: str | None = None) -> int:
        tenant = tenant_id or self.DEFAULT_TENANT
        container = self._container()
        items = list(
            container.query_items(
                query="SELECT c.id, c.conversationId FROM c",
                partition_key=[tenant, user_id],
            )
        )
        for item in items:
            container.delete_item(
                item["id"], partition_key=[tenant, user_id, item["conversationId"]]
            )
        logger.info("cleared %d messages for user %s", len(items), user_id)
        return len(items)
