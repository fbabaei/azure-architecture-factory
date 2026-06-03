"""Hybrid retrieval over the Casewright Azure AI Search index.

Implements the query side of the retrieval design: vector + keyword (hybrid) search with the
semantic reranker, filtering out any result below the configured minimum reranker score so the
agent is only ever grounded on high-confidence passages.
"""
from __future__ import annotations

import logging

from casewright.core.clients import get_openai_client, get_search_client
from casewright.core.models import Citation
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)


class RetrievedPassage:
    def __init__(self, content: str, title: str, source_path: str, score: float):
        self.content = content
        self.title = title
        self.source_path = source_path
        self.score = score

    def as_citation(self) -> Citation:
        return Citation(
            document_title=self.title, source_path=self.source_path, score=self.score
        )


def _embed(text: str) -> list[float]:
    s = get_settings()
    client = get_openai_client()
    result = client.embeddings.create(
        model=s.embedding_deployment,
        input=text,
        dimensions=s.embedding_dimensions,
    )
    return result.data[0].embedding


def retrieve(query: str) -> list[RetrievedPassage]:
    """Run a hybrid + semantic query and return passages above the reranker threshold."""
    s = get_settings()
    client = get_search_client()

    from azure.search.documents.models import VectorizedQuery

    vector_query = VectorizedQuery(
        vector=_embed(query),
        k_nearest_neighbors=s.search_top_k,
        fields="content_embedding",
    )

    results = client.search(
        search_text=query,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="casewright-semantic",
        top=s.search_top_k,
        select=["content_text", "document_title", "source_path"],
    )

    passages: list[RetrievedPassage] = []
    for doc in results:
        reranker_score = doc.get("@search.reranker_score")
        if reranker_score is None or reranker_score < s.min_reranker_score:
            continue
        passages.append(
            RetrievedPassage(
                content=doc.get("content_text", ""),
                title=doc.get("document_title", "Untitled"),
                source_path=doc.get("source_path", ""),
                score=float(reranker_score),
            )
        )

    logger.info("retrieve: %d passages above reranker threshold %.2f", len(passages), s.min_reranker_score)
    return passages
