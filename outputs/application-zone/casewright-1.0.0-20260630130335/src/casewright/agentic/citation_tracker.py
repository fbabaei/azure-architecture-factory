"""Citation tracking utilities for source attribution (ported from case-assistant-agent)."""
from __future__ import annotations

import logging

from casewright.agentic.models import Citation, RetrievedDocument

logger = logging.getLogger(__name__)


class CitationTracker:
    """Tracks citations and maintains source attribution throughout the pipeline."""

    def __init__(self) -> None:
        # Keyed by content_id — the stable unique identifier for a document chunk.
        self.documents: dict[str, RetrievedDocument] = {}

    def add_documents(self, documents: list[RetrievedDocument]) -> None:
        """Add documents to the tracker, skipping already-tracked ones."""
        for doc in documents:
            if doc.content_id not in self.documents:
                self.documents[doc.content_id] = doc

    def create_citations(self, documents: list[RetrievedDocument]) -> list[Citation]:
        """Create ``Citation`` objects for the provided documents."""
        return [
            Citation(
                document_id=doc.document_id,
                content_id=doc.content_id,
                content=doc.content,
                document_title=doc.title,
                page_number=doc.page_number,
            )
            for doc in documents
        ]

    def get_document_by_content_id(self, content_id: str) -> RetrievedDocument | None:
        """Look up a tracked document by its content ID."""
        return self.documents.get(content_id)

    def get_all_documents(self) -> list[RetrievedDocument]:
        """Return all currently tracked documents."""
        return list(self.documents.values())

    def get_document_count(self) -> int:
        """Return the total number of tracked documents."""
        return len(self.documents)
