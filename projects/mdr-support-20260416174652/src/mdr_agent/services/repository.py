"""Persistence for arrangement drafts and chat sessions.

Uses Cosmos DB when configured, otherwise an in-process dictionary so
local development and tests work without Azure dependencies.
"""
from __future__ import annotations

import logging
import uuid
from typing import Protocol

from ..config import Settings
from ..models import ChatTurn, MDRArrangement

logger = logging.getLogger(__name__)


class ArrangementRepository(Protocol):
    def save(self, arrangement: MDRArrangement) -> None: ...
    def get(self, arrangement_id: str) -> MDRArrangement | None: ...
    def delete(self, arrangement_id: str) -> bool: ...
    def append_turn(self, arrangement_id: str, turn: ChatTurn) -> None: ...
    def get_turns(self, arrangement_id: str) -> list[ChatTurn]: ...
    def clear_turns(self, arrangement_id: str) -> None: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._arrangements: dict[str, MDRArrangement] = {}
        self._turns: dict[str, list[ChatTurn]] = {}

    def save(self, arrangement: MDRArrangement) -> None:
        if not arrangement.arrangement_id:
            raise ValueError("arrangement_id is required")
        self._arrangements[arrangement.arrangement_id] = arrangement

    def get(self, arrangement_id: str) -> MDRArrangement | None:
        return self._arrangements.get(arrangement_id)

    def delete(self, arrangement_id: str) -> bool:
        existed = arrangement_id in self._arrangements or arrangement_id in self._turns
        self._arrangements.pop(arrangement_id, None)
        self._turns.pop(arrangement_id, None)
        return existed

    def append_turn(self, arrangement_id: str, turn: ChatTurn) -> None:
        self._turns.setdefault(arrangement_id, []).append(turn)

    def get_turns(self, arrangement_id: str) -> list[ChatTurn]:
        return list(self._turns.get(arrangement_id, []))

    def clear_turns(self, arrangement_id: str) -> None:
        self._turns.pop(arrangement_id, None)


class CosmosRepository:
    def __init__(self, settings: Settings) -> None:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        client = CosmosClient(url=settings.cosmos_endpoint, credential=credential)
        database = client.get_database_client(settings.cosmos_database)
        self._arrangements = database.get_container_client(
            settings.cosmos_arrangements_container
        )
        self._sessions = database.get_container_client(
            settings.cosmos_sessions_container
        )

    def save(self, arrangement: MDRArrangement) -> None:
        if not arrangement.arrangement_id:
            raise ValueError("arrangement_id is required")
        self._arrangements.upsert_item(
            {"id": arrangement.arrangement_id, **arrangement.model_dump(mode="json")}
        )

    def get(self, arrangement_id: str) -> MDRArrangement | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            item = self._arrangements.read_item(
                item=arrangement_id, partition_key=arrangement_id
            )
        except CosmosResourceNotFoundError:
            return None
        return MDRArrangement.model_validate(item)

    def delete(self, arrangement_id: str) -> bool:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        existed = False
        try:
            self._arrangements.delete_item(item=arrangement_id, partition_key=arrangement_id)
            existed = True
        except CosmosResourceNotFoundError:
            existed = False

        self.clear_turns(arrangement_id)
        return existed

    def append_turn(self, arrangement_id: str, turn: ChatTurn) -> None:
        # Each turn is a separate document for append-only semantics.
        self._sessions.create_item(
            {
                "id": f"{arrangement_id}:{turn.timestamp.isoformat()}:{uuid.uuid4().hex[:8]}",
                "arrangement_id": arrangement_id,
                **turn.model_dump(mode="json"),
            }
        )

    def get_turns(self, arrangement_id: str) -> list[ChatTurn]:
        query = "SELECT * FROM c WHERE c.arrangement_id = @id ORDER BY c.timestamp ASC"
        items = self._sessions.query_items(
            query=query,
            parameters=[{"name": "@id", "value": arrangement_id}],
            enable_cross_partition_query=True,
        )
        return [ChatTurn.model_validate(item) for item in items]

    def clear_turns(self, arrangement_id: str) -> None:
        query = "SELECT c.id, c.arrangement_id FROM c WHERE c.arrangement_id = @id"
        items = self._sessions.query_items(
            query=query,
            parameters=[{"name": "@id", "value": arrangement_id}],
            enable_cross_partition_query=True,
        )
        for item in items:
            self._sessions.delete_item(item=item["id"], partition_key=arrangement_id)


def build_repository(settings: Settings) -> ArrangementRepository:
    if settings.cosmos_endpoint:
        logger.info("Using Cosmos DB repository")
        return CosmosRepository(settings)
    logger.info("Using in-memory repository (local fallback)")
    return InMemoryRepository()
