"""Human-in-the-loop chat orchestration.

The chat service threads user answers back into the arrangement draft,
re-runs the clarification loop, and returns the next assistant prompt.
A production deployment would call Azure OpenAI for natural-language
reformulation; this service stays focused on the state machine so it is
deterministic and testable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import (
    ChatResponse,
    ChatTurn,
    ClarificationBundle,
    MDRArrangement,
)
from .clarification_service import build_clarifications
from .repository import ArrangementRepository


def _apply_answer_to_arrangement(
    arrangement: MDRArrangement, field: str, answer: str
) -> MDRArrangement:
    """Merge a single user answer into the arrangement draft.

    This is intentionally conservative — it only fills scalar string
    fields directly. Structured fields (hallmarks, parties, jurisdictions)
    expect a later LLM parse step, which we stub here with a simple
    comma-split for jurisdictions to keep the happy path testable.
    """
    data = arrangement.model_dump()
    if field in ("reference", "summary"):
        data[field] = answer.strip()
    elif field == "implementation_date":
        data[field] = answer.strip()
    elif field == "jurisdictions":
        data[field] = [
            code.strip().upper()
            for code in answer.replace(";", ",").split(",")
            if code.strip()
        ]
    elif field == "hallmarks":
        data[field] = [
            {"code": code.strip().upper(), "category": code.strip()[0].upper()}
            for code in answer.replace(";", ",").split(",")
            if code.strip()
        ]
    elif field == "parties":
        # Parse as a comma/semicolon separated list of party names. A
        # production impl would dispatch an LLM structured-extraction
        # call to resolve role / jurisdiction / TIN.
        data[field] = [
            {"role": "relevant_taxpayer", "name": name.strip()}
            for name in answer.replace(";", ",").split(",")
            if name.strip()
        ]
    return MDRArrangement.model_validate(data)


def _next_field(bundle: ClarificationBundle) -> str | None:
    return bundle.missing_fields[0] if bundle.missing_fields else None


def handle_chat_turn(
    *,
    arrangement_id: str,
    user_message: str,
    repository: ArrangementRepository,
) -> ChatResponse:
    arrangement = repository.get(arrangement_id)
    if arrangement is None:
        raise ValueError(f"Unknown arrangement_id: {arrangement_id}")

    repository.append_turn(
        arrangement_id,
        ChatTurn(
            role="user",
            content=user_message,
            timestamp=datetime.now(timezone.utc),
        ),
    )

    # Which field was the user answering? Look at the most recent missing
    # field list before applying their response.
    pre_bundle = build_clarifications(arrangement)
    answered_field = _next_field(pre_bundle)

    if answered_field is not None:
        arrangement = _apply_answer_to_arrangement(
            arrangement, answered_field, user_message
        )
        arrangement.arrangement_id = arrangement_id
        repository.save(arrangement)

    post_bundle = build_clarifications(arrangement)
    post_bundle = ClarificationBundle.model_validate(
        {**post_bundle.model_dump(), "arrangement_id": arrangement_id}
    )

    if post_bundle.is_complete:
        reply = (
            "Thanks — I have everything I need. You can now generate the arrangement draft."
        )
    else:
        next_q = post_bundle.questions[0]
        reply = next_q.question + (f" ({next_q.hint})" if next_q.hint else "")

    repository.append_turn(
        arrangement_id,
        ChatTurn(
            role="assistant",
            content=reply,
            timestamp=datetime.now(timezone.utc),
        ),
    )

    return ChatResponse(
        arrangement_id=arrangement_id,
        reply=reply,
        arrangement=arrangement,
        clarifications=post_bundle,
    )
