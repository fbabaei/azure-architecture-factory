"""Search index definition.

Vector dimensions come from settings (never hardcoded) so the embedding model can change
without an index rebuild edit. HNSW + scalar quantization for the vector field, plus a semantic
configuration that powers the reranker used on the query side.
"""
from __future__ import annotations

import logging

from casewright.core.clients import get_search_index_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

VECTOR_PROFILE = "casewright-hnsw"
SEMANTIC_CONFIG = "casewright-semantic"


def build_index():
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        ScalarQuantizationCompression,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    s = get_settings()

    fields = [
        SimpleField(name="content_id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content_text", type=SearchFieldDataType.String),
        SearchableField(name="document_title", type=SearchFieldDataType.String),
        SimpleField(name="source_path", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="site_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="content_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="last_modified", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        SearchField(
            name="content_embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=s.embedding_dimensions,
            vector_search_profile_name=VECTOR_PROFILE,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="casewright-hnsw-algo")],
        compressions=[ScalarQuantizationCompression(compression_name="casewright-scalar")],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE,
                algorithm_configuration_name="casewright-hnsw-algo",
                compression_name="casewright-scalar",
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name=SEMANTIC_CONFIG,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="document_title"),
                    content_fields=[SemanticField(field_name="content_text")],
                ),
            )
        ]
    )

    return SearchIndex(
        name=s.search_index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )


def ensure_index() -> None:
    """Create-or-update the index. Idempotent."""
    client = get_search_index_client()
    index = build_index()
    client.create_or_update_index(index)
    logger.info("ensured index %s", index.name)
