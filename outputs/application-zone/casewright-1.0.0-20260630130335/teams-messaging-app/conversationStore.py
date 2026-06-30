"""Durable conversation-reference store for proactive Teams messaging.

Proactive messaging requires durable, shared state — never in-memory, which
is lost on restart/scale-out, and the sending process is often not the
receiving one (Phase 5 of the deployment guide).

This module provides:

- :class:`IConversationStore` — the protocol the messenger depends on.
- :class:`InMemoryConversationStore` — a process-local fallback used when
  Cosmos DB is not configured (e.g. local Agents Playground testing).
- :class:`CosmosConversationStore` — the production store backed by a Cosmos
  container (partition key ``/userKey``, one document per user).

The Cosmos SDK is synchronous; calls are dispatched through
``asyncio.to_thread`` so the Teams event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversationRecord:
    """A user's stored conversation reference for proactive sends."""

    user_key: str
    conversation_id: str
    tenant_id: str | None = None
    service_url: str | None = None
    channel_id: str | None = None
    bot_id: str | None = None
    foundry_conversation_id: str | None = None
    installed: bool = True
    updated_at: str | None = None


class IConversationStore(Protocol):
    async def upsert(
        self,
        *,
        user_key: str,
        conversation_id: str,
        tenant_id: str | None = None,
        service_url: str | None = None,
        channel_id: str | None = None,
        bot_id: str | None = None,
        foundry_conversation_id: str | None = None,
        installed: bool = True,
    ) -> None: ...

    async def get(self, user_key: str) -> ConversationRecord | None: ...

    async def mark_uninstalled(self, user_key: str) -> None: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryConversationStore:
    """Process-local store. Not durable — for local/dev use only."""

    def __init__(self) -> None:
        self._records: dict[str, ConversationRecord] = {}

    async def upsert(
        self,
        *,
        user_key: str,
        conversation_id: str,
        tenant_id: str | None = None,
        service_url: str | None = None,
        channel_id: str | None = None,
        bot_id: str | None = None,
        foundry_conversation_id: str | None = None,
        installed: bool = True,
    ) -> None:
        if not user_key:
            return
        existing = self._records.get(user_key)
        self._records[user_key] = ConversationRecord(
            user_key=user_key,
            conversation_id=conversation_id,
            # Refresh rotating fields; preserve prior values when not supplied.
            tenant_id=tenant_id or (existing.tenant_id if existing else None),
            service_url=service_url or (existing.service_url if existing else None),
            channel_id=channel_id or (existing.channel_id if existing else None),
            bot_id=bot_id or (existing.bot_id if existing else None),
            foundry_conversation_id=(
                foundry_conversation_id
                or (existing.foundry_conversation_id if existing else None)
            ),
            installed=installed,
            updated_at=_now_iso(),
        )

    async def get(self, user_key: str) -> ConversationRecord | None:
        return self._records.get(user_key)

    async def mark_uninstalled(self, user_key: str) -> None:
        existing = self._records.get(user_key)
        if existing:
            self._records[user_key] = ConversationRecord(
                **{**existing.__dict__, "installed": False, "updated_at": _now_iso()}
            )


class CosmosConversationStore:
    """Cosmos-backed conversation-reference store.

    Container ``conversation_references`` with partition key ``/userKey`` and
    one document per user. Authenticates with ``DefaultAzureCredential`` (AAD)
    when no key is supplied, otherwise with the account key.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        database: str,
        container: str,
        key: str | None = None,
    ) -> None:
        # Imported lazily so the in-memory path has no hard dependency on the
        # azure-cosmos package.
        from azure.cosmos import CosmosClient

        if key:
            client = CosmosClient(url=endpoint, credential=key)
        else:
            from azure.identity import DefaultAzureCredential

            client = CosmosClient(url=endpoint, credential=DefaultAzureCredential())

        self._container = client.get_database_client(database).get_container_client(
            container
        )

    async def upsert(
        self,
        *,
        user_key: str,
        conversation_id: str,
        tenant_id: str | None = None,
        service_url: str | None = None,
        channel_id: str | None = None,
        bot_id: str | None = None,
        foundry_conversation_id: str | None = None,
        installed: bool = True,
    ) -> None:
        if not user_key:
            return
        await asyncio.to_thread(
            self._upsert_sync,
            user_key,
            conversation_id,
            tenant_id,
            service_url,
            channel_id,
            bot_id,
            foundry_conversation_id,
            installed,
        )

    async def get(self, user_key: str) -> ConversationRecord | None:
        if not user_key:
            return None
        doc = await asyncio.to_thread(self._read_sync, user_key)
        return _doc_to_record(doc) if doc else None

    async def mark_uninstalled(self, user_key: str) -> None:
        if not user_key:
            return
        await asyncio.to_thread(self._mark_uninstalled_sync, user_key)

    # ---- sync internals dispatched via asyncio.to_thread ---- #

    def _read_sync(self, user_key: str) -> dict | None:
        from azure.cosmos import exceptions as cosmos_exceptions

        try:
            return self._container.read_item(item=user_key, partition_key=user_key)
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None

    def _upsert_sync(
        self,
        user_key: str,
        conversation_id: str,
        tenant_id: str | None,
        service_url: str | None,
        channel_id: str | None,
        bot_id: str | None,
        foundry_conversation_id: str | None,
        installed: bool,
    ) -> None:
        existing = self._read_sync(user_key) or {}
        doc = {
            "id": user_key,
            "userKey": user_key,
            "conversationId": conversation_id,
            # Refresh rotating fields; preserve prior values when not supplied.
            "tenantId": tenant_id or existing.get("tenantId"),
            "serviceUrl": service_url or existing.get("serviceUrl"),
            "channelId": channel_id or existing.get("channelId"),
            "botId": bot_id or existing.get("botId"),
            "foundryConversationId": (
                foundry_conversation_id or existing.get("foundryConversationId")
            ),
            "installed": installed,
            "updatedAt": _now_iso(),
        }
        self._container.upsert_item(doc)

    def _mark_uninstalled_sync(self, user_key: str) -> None:
        doc = self._read_sync(user_key)
        if not doc:
            return
        doc["installed"] = False
        doc["updatedAt"] = _now_iso()
        self._container.upsert_item(doc)


def _doc_to_record(doc: dict) -> ConversationRecord:
    return ConversationRecord(
        user_key=doc.get("userKey") or doc.get("id", ""),
        conversation_id=doc.get("conversationId", ""),
        tenant_id=doc.get("tenantId"),
        service_url=doc.get("serviceUrl"),
        channel_id=doc.get("channelId"),
        bot_id=doc.get("botId"),
        foundry_conversation_id=doc.get("foundryConversationId"),
        installed=bool(doc.get("installed", True)),
        updated_at=doc.get("updatedAt"),
    )


def build_conversation_store(
    *,
    cosmos_endpoint: str | None,
    cosmos_database: str | None,
    cosmos_container: str | None,
    cosmos_key: str | None = None,
) -> IConversationStore:
    """Return a Cosmos store when fully configured, else an in-memory store."""
    if cosmos_endpoint and cosmos_database and cosmos_container:
        logger.info(
            "Using Cosmos conversation store (container=%s)", cosmos_container
        )
        return CosmosConversationStore(
            endpoint=cosmos_endpoint,
            database=cosmos_database,
            container=cosmos_container,
            key=cosmos_key,
        )
    logger.warning(
        "Cosmos not configured — using in-memory conversation store "
        "(not durable; proactive sends are lost on restart/scale-out)."
    )
    return InMemoryConversationStore()
