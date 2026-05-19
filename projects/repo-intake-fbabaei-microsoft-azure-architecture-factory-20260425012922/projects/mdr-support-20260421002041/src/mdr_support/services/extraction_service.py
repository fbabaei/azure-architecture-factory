"""Structured extraction stub.

Replace ``extract_structured_data`` with an Azure OpenAI / Foundry call
that emits the same ExtractionResult shape in production.
"""
from __future__ import annotations

import re

from ..models import ExtractionResult
from .document_ingestion import IngestedDocument

MANDATORY_FIELDS = ("reference_id", "submission_date", "jurisdiction", "summary")


def extract_structured_data(doc: IngestedDocument) -> ExtractionResult:
    text = doc.text_excerpt or ""
    fields: dict[str, str] = {}
    ref = re.search(r"\b(?:ref|reference)\s*[:#]?\s*([A-Z0-9\-]{4,})", text, re.IGNORECASE)
    if ref:
        fields["reference_id"] = ref.group(1)
    date = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if date:
        fields["submission_date"] = date.group(1)
    jurisdiction = re.search(r"\bjurisdiction\s*[:=]?\s*([A-Za-z ]{2,40})", text, re.IGNORECASE)
    if jurisdiction:
        fields["jurisdiction"] = jurisdiction.group(1).strip()
    if text:
        fields["summary"] = text[:200]
    return ExtractionResult(fields=fields, raw_excerpt=text[:500])
