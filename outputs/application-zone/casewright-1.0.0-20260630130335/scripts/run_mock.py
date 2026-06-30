"""Run Casewright locally with mock data — no Azure connectivity required.

This serves the real FastAPI app (and its built-in chat UI at ``/``) but swaps the two
call-time collaborators that would otherwise need Azure:

* the chat-history repository -> an in-memory store, and
* the case-knowledge agent -> a mock that retrieves over a handful of seeded case
  documents and returns a grounded answer with citations.

Everything else (routers, models, static UI) is exercised exactly as in production, so you
get a faithful end-to-end feel of the grounded-chat experience without provisioning anything.

Usage (from projects/casewright):

    python scripts/run_mock.py
    # open http://localhost:8000/

"""
from __future__ import annotations

import uvicorn

from casewright.api.routers import chat as chat_router
from casewright.core.models import ChatResponse, ChatTurn

# --------------------------------------------------------------------------------------
# Seed "case knowledge base" — a few sample documents the mock agent retrieves over.
# --------------------------------------------------------------------------------------
SEED_DOCS: list[dict[str, str]] = [
    {
        "title": "Refund Policy — Standard Orders",
        "path": "policies/refunds/standard.md",
        "content": (
            "Customers may request a full refund within 30 days of delivery for unused items "
            "in original packaging. Refunds are issued to the original payment method within "
            "5-7 business days. Shipping fees are non-refundable unless the return is due to a "
            "defect or shipping error."
        ),
    },
    {
        "title": "Refund Policy — Digital Goods",
        "path": "policies/refunds/digital.md",
        "content": (
            "Digital goods (downloads, license keys, subscriptions) are generally "
            "non-refundable once delivered or activated. An exception applies when the product "
            "is defective and cannot be made to work after support engagement; in that case a "
            "refund or replacement license is offered within 14 days of purchase."
        ),
    },
    {
        "title": "Case Handling SLA",
        "path": "operations/sla.md",
        "content": (
            "Priority 1 (service down) cases require first response within 1 hour and "
            "resolution targeted within 8 hours. Priority 2 cases require first response within "
            "4 business hours. All cases must record a resolution summary before they can be "
            "closed."
        ),
    },
    {
        "title": "Escalation Procedure",
        "path": "operations/escalation.md",
        "content": (
            "If a Priority 1 case is not acknowledged within the 1-hour SLA, it auto-escalates "
            "to the on-call lead. Customer-requested escalations are routed to a team lead who "
            "must respond within 2 business hours. Every escalation is logged with a reason "
            "code for monthly review."
        ),
    },
    {
        "title": "Warranty Coverage",
        "path": "policies/warranty.md",
        "content": (
            "Hardware carries a 12-month limited warranty covering manufacturing defects. "
            "Accidental damage and normal wear are excluded. Warranty claims require the order "
            "number and proof of purchase; approved claims are repaired or replaced at no cost."
        ),
    },
]

_STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "to", "for", "and", "or", "in", "on", "what",
    "how", "do", "does", "can", "i", "my", "we", "you", "it", "be", "with", "about",
}


def _tokens(text: str) -> set[str]:
    return {
        t.strip(".,?!()[]\"'").lower()
        for t in text.split()
        if t.strip(".,?!()[]\"'").lower() not in _STOPWORDS and len(t) > 1
    }


class _MockHistory:
    """In-memory chat history keyed by conversation id."""

    def __init__(self) -> None:
        self._store: dict[str, list[ChatTurn]] = {}

    async def get_turns(self, tenant_id: str, user_id: str, conversation_id: str) -> list[ChatTurn]:
        return list(self._store.get(conversation_id, []))

    async def append_turns(
        self, tenant_id: str, user_id: str, conversation_id: str, turns: list[ChatTurn]
    ) -> None:
        self._store.setdefault(conversation_id, []).extend(turns)


class _MockAgent:
    """Retrieves over SEED_DOCS by token overlap and returns a grounded mock answer."""

    async def answer(self, request, history):  # noqa: ANN001 - mirrors real agent signature
        query_tokens = _tokens(request.message)
        scored = []
        for doc in SEED_DOCS:
            overlap = len(query_tokens & _tokens(f"{doc['title']} {doc['content']}"))
            if overlap:
                scored.append((overlap, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [doc for _, doc in scored[:3]]

        if top:
            grounding = "\n".join(f"- {d['title']}: {d['content']}" for d in top)
            answer = (
                f"Based on the case knowledge base, here is what applies to "
                f"\u201c{request.message.strip()}\u201d:\n\n{grounding}\n\n"
                "(Mock answer — generated locally from seeded documents, no Azure calls.)"
            )
            citations = [
                {"document_title": d["title"], "source_path": d["path"], "score": 1.0}
                for d in top
            ]
        else:
            answer = (
                "I couldn't find anything relevant in the seeded case knowledge base. "
                "Try asking about refunds, warranty, SLA, or escalations.\n\n"
                "(Mock answer — no Azure calls.)"
            )
            citations = []

        return ChatResponse(
            conversation_id=request.conversation_id,
            answer=answer,
            citations=citations,
            runtime="local",
        )


def _install_mocks() -> None:
    history = _MockHistory()
    agent = _MockAgent()
    chat_router._get_history = lambda: history  # type: ignore[assignment]
    chat_router._get_agent = lambda: agent  # type: ignore[assignment]


def main() -> None:
    _install_mocks()
    # Import after mocks are installed so the app picks up the patched factories.
    from casewright.api.main import app

    import os

    port = int(os.environ.get("CASEWRIGHT_PORT", "8010"))
    host = os.environ.get("CASEWRIGHT_HOST", "0.0.0.0")
    print(f"Casewright (mock mode) — open http://localhost:{port}/")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
