"""Document ingestion stub.

Swap in Azure AI Document Intelligence / Form Recognizer in production.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IngestedDocument:
    filename: str
    content_type: str
    text_excerpt: str
    notes: str


def ingest_document(filename: str, payload: bytes, notes: str = "") -> IngestedDocument:
    lowered = filename.lower()
    if lowered.endswith(".pdf"):
        content_type = "application/pdf"
        text_excerpt = "[pdf: " + str(len(payload)) + " bytes -- replace ingestion stub with OCR]"
    elif lowered.endswith((".doc", ".docx")):
        content_type = "application/msword"
        text_excerpt = "[word doc: " + str(len(payload)) + " bytes -- replace ingestion stub]"
    else:
        content_type = "text/plain"
        try:
            text_excerpt = payload.decode("utf-8", errors="replace")[:2000]
        except Exception:
            text_excerpt = ""
    return IngestedDocument(filename=filename, content_type=content_type, text_excerpt=text_excerpt, notes=notes)
