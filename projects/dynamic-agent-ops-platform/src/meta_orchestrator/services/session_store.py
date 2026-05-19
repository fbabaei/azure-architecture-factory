"""Session state store — Cosmos DB backed with in-memory fallback for local dev."""
from __future__ import annotations

import json
import logging
from typing import Optional

from meta_orchestrator.config import Settings
from meta_orchestrator.models import SessionState

logger = logging.getLogger(__name__)

_LOCAL_STORE: dict[str, dict] = {}  # in-memory fallback for local dev


class SessionStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._container = None
        if settings.cosmos_endpoint:
            self._container = self._init_cosmos(settings)

    def _init_cosmos(self, settings: Settings):
        try:
            from azure.cosmos.aio import CosmosClient  # type: ignore[import]
            from azure.identity.aio import DefaultAzureCredential  # type: ignore[import]

            client = CosmosClient(
                settings.cosmos_endpoint, credential=DefaultAzureCredential()
            )
            db = client.get_database_client(settings.cosmos_database)
            return db.get_container_client("agent_sessions")
        except Exception as exc:
            logger.warning("Cosmos DB init failed (%s); using in-memory store.", exc)
            return None

    async def save(self, state: SessionState) -> None:
        doc = state.model_dump(mode="json")
        doc["id"] = state.session_id
        if self._container is not None:
            try:
                await self._container.upsert_item(doc)
                return
            except Exception as exc:
                logger.warning("Cosmos upsert failed (%s); falling back to memory.", exc)
        _LOCAL_STORE[state.session_id] = doc

    async def get(self, session_id: str) -> Optional[SessionState]:
        if self._container is not None:
            try:
                doc = await self._container.read_item(session_id, partition_key=session_id)
                return SessionState(**doc)
            except Exception as exc:
                logger.warning("Cosmos read failed (%s); checking memory.", exc)
        doc = _LOCAL_STORE.get(session_id)
        if doc:
            return SessionState(**doc)
        return None
