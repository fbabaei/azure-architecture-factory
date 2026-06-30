"""Cosmos-backed high-water-mark store for SharePoint delta-sync.

Holds, per (tenant, site), the map of item id -> eTag observed on the last sync. The delta-sync
reads this to classify added/updated/unchanged/deleted, then writes the fresh map back. One item
per site keeps reads/writes to a single point operation. AAD auth only.
"""
from __future__ import annotations

import logging

from azure.cosmos import exceptions as cosmos_exceptions

from casewright.core.clients import get_cosmos_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)


class SyncStateRepository:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = get_cosmos_client()

    def _container(self):
        s = self._settings
        db = self._client.get_database_client(s.cosmos_database)
        return db.get_container_client(s.cosmos_sync_state_container)

    @staticmethod
    def _doc_id(site_id: str) -> str:
        return f"site::{site_id}"

    async def get_site_state(self, tenant_id: str, site_id: str) -> dict[str, str]:
        container = self._container()
        try:
            item = container.read_item(item=self._doc_id(site_id), partition_key=tenant_id)
            return item.get("etags", {})
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return {}

    async def put_site_state(self, tenant_id: str, site_id: str, etags: dict[str, str]) -> None:
        container = self._container()
        container.upsert_item(
            {
                "id": self._doc_id(site_id),
                "tenantId": tenant_id,
                "siteId": site_id,
                "etags": etags,
            }
        )
        logger.info("persisted %d etags for site %s", len(etags), site_id)
