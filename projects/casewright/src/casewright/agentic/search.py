"""Hybrid search service for the agentic RAG engine.

Wraps Casewright's existing managed-identity ``SearchClient`` / ``AzureOpenAI`` clients and
maps the Casewright index schema (``content_id`` / ``content_text`` / ``document_title`` /
``source_path`` / ``content_type`` / ``last_modified``) onto the ``RetrievedDocument`` model the
agentic workflow expects. Supports OData filters and per-iteration exclusion of already-seen
chunks so each retry surfaces fresh results.
"""
from __future__ import annotations

import logging
from typing import Any

from casewright.agentic.models import RetrievedDocument
from casewright.core.clients import get_openai_client, get_search_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

_SELECT_FIELDS = [
    "content_id",
    "content_text",
    "document_title",
    "source_path",
    "content_type",
    "last_modified",
]


def _escape_odata(value: str) -> str:
    """Escape single quotes for an OData string literal."""
    return value.replace("'", "''")


def _build_filter(filters: dict[str, Any] | None, exclude_ids: list[str] | None) -> str | None:
    """Build an OData ``$filter`` expression from the request filters + exclusion list."""
    clauses: list[str] = []

    if filters:
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")
        document_type = filters.get("document_type")
        custom = filters.get("custom")

        if date_from:
            clauses.append(f"last_modified ge {date_from}")
        if date_to:
            clauses.append(f"last_modified le {date_to}")
        if document_type:
            clauses.append(f"content_type eq '{_escape_odata(document_type)}'")
        # 'category' has no corresponding field in the Casewright index; ignored intentionally.
        if filters.get("category"):
            logger.info("search: 'category' filter ignored (no matching field in index)")
        if custom:
            clauses.append(f"({custom})")

    if exclude_ids:
        # content_id is the key field (filterable). Exclude already-processed chunks.
        joined = ",".join(_escape_odata(cid) for cid in exclude_ids)
        clauses.append(f"not search.in(content_id, '{joined}', ',')")

    if not clauses:
        return None
    return " and ".join(clauses)


class AgenticSearchService:
    """Hybrid (vector + keyword) + semantic search returning ``RetrievedDocument`` objects."""

    def _embed(self, text: str) -> list[float]:
        s = get_settings()
        client = get_openai_client()
        result = client.embeddings.create(
            model=s.embedding_deployment,
            input=text,
            dimensions=s.embedding_dimensions,
        )
        return result.data[0].embedding

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        exclude_ids: list[str] | None = None,
    ) -> list[RetrievedDocument]:
        """Run a hybrid + semantic query and return passages above the reranker threshold."""
        s = get_settings()
        client = get_search_client()

        from azure.search.documents.models import VectorizedQuery

        vector_query = VectorizedQuery(
            vector=self._embed(query),
            k_nearest_neighbors=top_k,
            fields="content_embedding",
        )

        odata_filter = _build_filter(filters, exclude_ids)

        results = client.search(
            search_text=query,
            vector_queries=[vector_query],
            query_type="semantic",
            semantic_configuration_name=s.semantic_configuration_name,
            top=top_k,
            filter=odata_filter,
            select=_SELECT_FIELDS,
        )

        passages: list[RetrievedDocument] = []
        for doc in results:
            reranker_score = doc.get("@search.reranker_score")
            if reranker_score is None or reranker_score < s.min_reranker_score:
                continue
            content_id = doc.get("content_id", "")
            source_path = doc.get("source_path", "")
            passages.append(
                RetrievedDocument(
                    document_id=source_path or content_id,
                    content_id=content_id,
                    title=doc.get("document_title", "Untitled"),
                    content=doc.get("content_text", ""),
                    source=source_path,
                    page_number=None,
                    score=float(doc.get("@search.score") or 0.0),
                    reranker_score=float(reranker_score),
                    metadata={"content_type": doc.get("content_type", "")},
                )
            )

        logger.info(
            "agentic search: %d passages above reranker threshold %.2f (filter=%s)",
            len(passages),
            s.min_reranker_score,
            bool(odata_filter),
        )
        return passages
