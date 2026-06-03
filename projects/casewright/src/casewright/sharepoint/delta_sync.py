"""Incremental SharePoint → Blob synchronization.

For each site we compare the current Graph file listing against the last-known state stored in
Cosmos (keyed by item id, holding the eTag/last-modified). Each file is classified:

    added      — id not seen before
    updated    — id seen, but eTag changed
    unchanged  — id seen, eTag identical
    deleted    — previously seen id no longer present in the listing

Only added/updated files are downloaded and uploaded to the ingestion Blob container; deleted
files are soft-deleted in Blob so the indexer's soft-delete policy removes them from the index.
The new state is persisted for the next run. The classification function is pure so it can be
unit-tested without any Azure calls.
"""
from __future__ import annotations

import logging

from casewright.core.clients import get_blob_service_client
from casewright.core.models import SyncRequest, SyncResult
from casewright.core.settings import get_settings
from casewright.repositories.sync_state import SyncStateRepository
from casewright.sharepoint.graph_client import SharePointGraphClient

logger = logging.getLogger(__name__)


def classify(
    current: dict[str, str], previous: dict[str, str]
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (added, updated, unchanged, deleted) item-id lists.

    `current` and `previous` map item id -> eTag.
    """
    added, updated, unchanged = [], [], []
    for item_id, etag in current.items():
        if item_id not in previous:
            added.append(item_id)
        elif previous[item_id] != etag:
            updated.append(item_id)
        else:
            unchanged.append(item_id)
    deleted = [item_id for item_id in previous if item_id not in current]
    return added, updated, unchanged, deleted


class SharePointDeltaSync:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._graph = SharePointGraphClient()
        self._state = SyncStateRepository()

    async def sync_site(self, request: SyncRequest) -> SyncResult:
        items = await self._graph.list_drive_items(request.site_id)
        current = {item["id"]: item.get("eTag", "") for item in items}
        item_by_id = {item["id"]: item for item in items}

        previous = await self._state.get_site_state(request.tenant_id, request.site_id)
        added, updated, unchanged, deleted = classify(current, previous)

        blob = get_blob_service_client().get_container_client(self._settings.ingestion_container)

        for item_id in added + updated:
            content = await self._graph.download_item(request.site_id, item_id)
            name = item_by_id[item_id].get("name", item_id)
            blob_name = f"{request.site_id}/{name}"
            blob.upload_blob(name=blob_name, data=content, overwrite=True)

        for item_id in deleted:
            # Soft-delete marker; the indexer's SoftDeleteColumnDeletionDetectionPolicy removes it.
            try:
                blob_client = blob.get_blob_client(f"{request.site_id}/{previous.get(item_id, item_id)}")
                blob_client.set_blob_metadata({"is_deleted": "true"})
            except Exception:  # pragma: no cover - best effort
                logger.warning("could not mark %s deleted", item_id)

        await self._state.put_site_state(request.tenant_id, request.site_id, current)

        result = SyncResult(
            site_id=request.site_id,
            added=len(added),
            updated=len(updated),
            unchanged=len(unchanged),
            deleted=len(deleted),
        )
        logger.info(
            "site %s sync: +%d ~%d =%d -%d",
            request.site_id, result.added, result.updated, result.unchanged, result.deleted,
        )
        return result
