"""Document ingestion: persist uploads to Blob Storage and extract raw text.

In production this uses Azure Blob Storage (for the source artifact) and
Azure AI Document Intelligence (for PDF layout + text). A local-fallback
path is kept so unit tests can exercise the orchestration without the
Azure dependencies configured.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from ..config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestedDocument:
    blob_name: str
    content_type: str
    text: str
    page_count: int


class DocumentIngestionService(Protocol):
    def ingest(
        self, *, arrangement_id: str, filename: str, content_type: str, data: bytes
    ) -> IngestedDocument: ...


class LocalDocumentIngestion:
    """Fallback ingestion used when Azure dependencies are not configured.

    Stores the upload in-memory and returns the decoded text. Good enough
    for the plain-text branch of the BRD ("PDFs and text inputs") during
    local development.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def ingest(
        self, *, arrangement_id: str, filename: str, content_type: str, data: bytes
    ) -> IngestedDocument:
        blob_name = f"{arrangement_id}/{filename}"
        self._store[blob_name] = data
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        return IngestedDocument(
            blob_name=blob_name,
            content_type=content_type,
            text=text,
            page_count=max(1, text.count("\f") + 1),
        )


class AzureDocumentIngestion:
    """Uploads to Blob Storage and runs Document Intelligence layout analysis."""

    def __init__(self, settings: Settings) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
        from azure.ai.documentintelligence import DocumentIntelligenceClient

        credential = DefaultAzureCredential()
        self._blob = BlobServiceClient(
            account_url=settings.blob_account_url, credential=credential
        )
        self._container = settings.blob_container
        self._doc_intel = DocumentIntelligenceClient(
            endpoint=settings.doc_intel_endpoint, credential=credential
        )

    def ingest(
        self, *, arrangement_id: str, filename: str, content_type: str, data: bytes
    ) -> IngestedDocument:
        blob_name = f"{arrangement_id}/{filename}"
        container = self._blob.get_container_client(self._container)
        container.upload_blob(name=blob_name, data=data, overwrite=True)

        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

        poller = self._doc_intel.begin_analyze_document(
            model_id="prebuilt-layout",
            body=AnalyzeDocumentRequest(bytes_source=data),
        )
        result = poller.result()
        pages = result.pages or []
        text = "\n".join(
            line.content for page in pages for line in (page.lines or [])
        )
        return IngestedDocument(
            blob_name=blob_name,
            content_type=content_type,
            text=text,
            page_count=len(pages),
        )


def build_ingestion_service(settings: Settings) -> DocumentIngestionService:
    if settings.azure_enabled and settings.doc_intel_endpoint:
        logger.info("Using Azure Blob + Document Intelligence for ingestion")
        return AzureDocumentIngestion(settings)
    logger.info("Using local in-memory ingestion fallback")
    return LocalDocumentIngestion()
