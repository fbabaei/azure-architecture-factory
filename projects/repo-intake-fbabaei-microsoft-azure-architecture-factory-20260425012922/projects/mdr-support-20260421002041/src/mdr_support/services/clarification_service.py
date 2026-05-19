"""Clarification service: compute the next missing mandatory field."""
from __future__ import annotations

from ..models import Clarification, ExtractionDraft
from .extraction_service import MANDATORY_FIELDS


_FIELD_PROMPTS: dict[str, str] = {
    "reference_id": "What is the reference ID for this submission?",
    "submission_date": "What is the submission date (YYYY-MM-DD)?",
    "jurisdiction": "Which jurisdiction does this arrangement apply to?",
    "summary": "Please provide a short summary of the arrangement.",
}


def compute_missing_fields(draft: ExtractionDraft) -> list[Clarification]:
    missing: list[Clarification] = []
    for field in MANDATORY_FIELDS:
        value = draft.fields.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(Clarification(field=field, prompt=_FIELD_PROMPTS.get(field, "Please provide a value.")))
    return missing
