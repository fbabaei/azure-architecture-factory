"""Blob data source connection for the indexers.

Uses the storage account's resource id with a managed-identity connection string (no account
key). Change tracking via HighWaterMark on the blob last-modified timestamp, and soft-delete
detection via a metadata column so deletions in SharePoint propagate to the index.
"""
from __future__ import annotations

import logging

from casewright.core.clients import get_search_indexer_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

DATASOURCE_NAME = "casewright-blob-datasource"


def ensure_datasource(storage_resource_id: str) -> None:
    from azure.search.documents.indexes.models import (
        DataChangeDetectionPolicy,
        HighWaterMarkChangeDetectionPolicy,
        SearchIndexerDataContainer,
        SearchIndexerDataSourceConnection,
        SoftDeleteColumnDeletionDetectionPolicy,
    )

    s = get_settings()
    client = get_search_indexer_client()

    change_policy: DataChangeDetectionPolicy = HighWaterMarkChangeDetectionPolicy(
        high_water_mark_column_name="metadata_storage_last_modified"
    )
    delete_policy = SoftDeleteColumnDeletionDetectionPolicy(
        soft_delete_column_name="is_deleted",
        soft_delete_marker_value="true",
    )

    datasource = SearchIndexerDataSourceConnection(
        name=DATASOURCE_NAME,
        type="azureblob",
        # Managed-identity connection string form: no account key embedded.
        connection_string=f"ResourceId={storage_resource_id};",
        container=SearchIndexerDataContainer(name=s.ingestion_container),
        data_change_detection_policy=change_policy,
        data_deletion_detection_policy=delete_policy,
    )
    client.create_or_update_data_source_connection(datasource)
    logger.info("ensured data source %s", DATASOURCE_NAME)
