"""Indexer definitions and the idempotent pipeline orchestrator.

Three indexers, one per content path (multimodal / markdown / json), each binding the shared
data source + index to its skillset. `setup()` creates-or-updates every component so it is safe
to call repeatedly. The orchestrator never embeds keys — the indexer authenticates to storage
and Azure OpenAI via the search service's managed identity.
"""
from __future__ import annotations

import asyncio
import logging

from casewright.core.clients import get_search_indexer_client
from casewright.core.models import IndexerStatus
from casewright.core.settings import get_settings
from casewright.ingestion.datasource import DATASOURCE_NAME, ensure_datasource
from casewright.ingestion.index import ensure_index
from casewright.ingestion.skillsets import (
    JSON_SKILLSET,
    MARKDOWN_SKILLSET,
    MULTIMODAL_SKILLSET,
    ensure_skillsets,
)

logger = logging.getLogger(__name__)

INDEXERS = {
    "casewright-multimodal-indexer": MULTIMODAL_SKILLSET,
    "casewright-markdown-indexer": MARKDOWN_SKILLSET,
    "casewright-json-indexer": JSON_SKILLSET,
}


def _ensure_indexers() -> None:
    from azure.search.documents.indexes.models import (
        FieldMapping,
        IndexingParameters,
        IndexingParametersConfiguration,
        SearchIndexer,
    )

    s = get_settings()
    client = get_search_indexer_client()

    for indexer_name, skillset_name in INDEXERS.items():
        parsing_mode = "json" if "json" in indexer_name else "default"
        indexer = SearchIndexer(
            name=indexer_name,
            data_source_name=DATASOURCE_NAME,
            target_index_name=s.search_index_name,
            skillset_name=skillset_name,
            parameters=IndexingParameters(
                configuration=IndexingParametersConfiguration(
                    parsing_mode=parsing_mode,
                    data_to_extract="contentAndMetadata",
                    query_timeout=None,
                )
            ),
            field_mappings=[
                FieldMapping(source_field_name="metadata_storage_path", target_field_name="source_path"),
                FieldMapping(source_field_name="metadata_storage_name", target_field_name="document_title"),
            ],
        )
        # Created disabled: runs are triggered explicitly by the worker only when there are net changes.
        indexer.is_disabled = True
        client.create_or_update_indexer(indexer)
        logger.info("ensured indexer %s", indexer_name)


class IngestionPipeline:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def setup(self, storage_resource_id: str | None = None) -> None:
        rid = storage_resource_id or self._settings.blob_account_url
        await asyncio.to_thread(self._setup_sync, rid)

    def _setup_sync(self, storage_resource_id: str) -> None:
        ensure_index()
        ensure_datasource(storage_resource_id)
        ensure_skillsets()
        _ensure_indexers()
        logger.info("ingestion pipeline configured")

    async def run_indexer(self, indexer_name: str) -> None:
        await asyncio.to_thread(self._run_indexer_sync, indexer_name)

    def _run_indexer_sync(self, indexer_name: str) -> None:
        client = get_search_indexer_client()
        client.run_indexer(indexer_name)
        logger.info("triggered indexer %s", indexer_name)

    async def get_indexer_status(self, indexer_name: str) -> IndexerStatus | None:
        return await asyncio.to_thread(self._get_status_sync, indexer_name)

    def _get_status_sync(self, indexer_name: str) -> IndexerStatus | None:
        client = get_search_indexer_client()
        try:
            status = client.get_indexer_status(indexer_name)
        except Exception:
            logger.exception("could not fetch status for %s", indexer_name)
            return None
        last = status.last_result
        return IndexerStatus(
            indexer_name=indexer_name,
            status=status.status,
            last_run=getattr(last, "end_time", None) if last else None,
            items_processed=getattr(last, "item_count", 0) if last else 0,
            items_failed=getattr(last, "failed_item_count", 0) if last else 0,
        )
