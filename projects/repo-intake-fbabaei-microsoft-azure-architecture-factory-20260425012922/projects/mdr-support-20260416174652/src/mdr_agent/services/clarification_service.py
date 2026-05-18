"""Clarification loop: detect missing mandatory fields and ask the user."""
from __future__ import annotations

from ..models import (
    ClarificationBundle,
    ClarificationQuestion,
    MANDATORY_FIELDS,
    MDRArrangement,
)


FIELD_QUESTIONS: dict[str, tuple[str, str | None]] = {
    "reference": (
        "What is the client or engagement reference for this arrangement?",
        "Example: EY-MDR-2026-0142",
    ),
    "summary": (
        "Can you provide a one-paragraph summary of the arrangement?",
        "Describe the purpose, structure, and tax effect.",
    ),
    "implementation_date": (
        "When was (or will be) the first step of the arrangement implemented?",
        "Use YYYY-MM-DD.",
    ),
    "hallmarks": (
        "Which DAC6 / MDR hallmarks apply (e.g. A1, B2, C1bi, D1)?",
        "Provide at least one category A–E hallmark.",
    ),
    "parties": (
        "Who are the parties involved (intermediaries, relevant taxpayers, associated enterprises)?",
        "Include name, role, and jurisdiction.",
    ),
    "jurisdictions": (
        "Which tax jurisdictions are concerned by this arrangement?",
        "Use ISO 3166 alpha-2 codes (e.g. DE, LU, IE).",
    ),
}


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, str)) and len(value) == 0:
        return True
    return False


def find_missing_fields(arrangement: MDRArrangement) -> list[str]:
    payload = arrangement.model_dump()
    return [field for field in MANDATORY_FIELDS if _is_missing(payload.get(field))]


def build_clarifications(arrangement: MDRArrangement) -> ClarificationBundle:
    missing = find_missing_fields(arrangement)
    questions = [
        ClarificationQuestion(
            field=field,
            question=FIELD_QUESTIONS[field][0],
            hint=FIELD_QUESTIONS[field][1],
        )
        for field in missing
    ]
    return ClarificationBundle(
        arrangement_id=arrangement.arrangement_id or "",
        missing_fields=missing,
        questions=questions,
        is_complete=not missing,
    )
