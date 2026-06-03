"""Agentic RAG workflow orchestrator (ported from case-assistant-agent).

Reproduces case-assistant-agent's MAF workflow (search → reflection → answer) as a plain
asynchronous loop driven by ``AgenticRAGState``. The loop:

1. **search**  – increments the attempt counter, applies the PII guard, optionally rewrites the
   query with HyDE, then retrieves fresh chunks (excluding already-processed content IDs).
2. **reflect** – reviews the current results, extends the vetted/discarded sets, and decides
   whether to retry retrieval or finalise (with smart-retry override).
3. **answer**  – formats the vetted results, generates a cited answer, and optionally redacts it.
"""
from __future__ import annotations

import logging
from typing import Any

from casewright.agentic.answer_generator import AnswerGenerator
from casewright.agentic.citation_tracker import CitationTracker
from casewright.agentic.models import AgenticRAGState, _utcnow
from casewright.agentic.pii import PIIDetectionService
from casewright.agentic.prompts import AnswerGeneratorPrompts
from casewright.agentic.query_rewriter import QueryRewriter
from casewright.agentic.reflection_agent import ReflectionAgent
from casewright.agentic.search import AgenticSearchService
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

_PII_REFUSAL = (
    "I'm unable to process this request because it appears to contain personal or sensitive "
    "information ({categories}). Please remove any personal data and try again."
)


def _format_vetted_results(results: list[Any]) -> str:
    if not results:
        return "(none)"
    blocks = []
    for i, doc in enumerate(results):
        blocks.append(
            f"Result #{i}\n"
            f"Content ID: {doc.content_id}\n"
            f"Document ID: {doc.document_id}\n"
            f"Title: {doc.title}\n"
            f"Source: {doc.source}\n"
            f"Page Number: {doc.page_number if doc.page_number is not None else 'N/A'}\n"
            f"Content: {doc.content}"
        )
    return "\n\n".join(blocks)


class AgenticRAGWorkflow:
    """Runs the retrieval/reflection/answer loop over a single query."""

    def __init__(self) -> None:
        self.query_rewriter = QueryRewriter()
        self.search_service = AgenticSearchService()
        self.reflection_agent = ReflectionAgent()
        self.citation_tracker = CitationTracker()
        self.answer_generator = AnswerGenerator(self.citation_tracker)
        self._pii_service: PIIDetectionService | None = None

    @property
    def pii_service(self) -> PIIDetectionService:
        if self._pii_service is None:
            self._pii_service = PIIDetectionService()
        return self._pii_service

    async def run(self, state: AgenticRAGState) -> AgenticRAGState:
        s = get_settings()
        max_attempts = state.max_attempts or s.workflow_max_retrieval_iterations

        while True:
            blocked = self._search_step(state, max_attempts)
            if blocked:
                # PII guard short-circuited the workflow with a refusal answer.
                return state

            route = self._reflect_step(state, max_attempts)
            if route == "search" and state.current_attempt < max_attempts:
                continue
            break

        self._answer_step(state)
        return state

    # ------------------------------------------------------------------ steps

    def _search_step(self, state: AgenticRAGState, max_attempts: int) -> bool:
        """Retrieve a fresh batch of chunks. Returns ``True`` if the PII guard blocked the query."""
        s = get_settings()
        state.current_attempt += 1

        search_query = state.query

        # PII guard (inbound query).
        if s.pii_active:
            try:
                result = self.pii_service.detect_pii(state.query)
            except Exception:  # noqa: BLE001 - never fail the request on PII service errors
                logger.warning("PII detection failed; continuing without guard", exc_info=True)
                result = None

            if result and result.contains_pii:
                if s.pii_block_on_detection or s.pii_mode == "block":
                    categories = ", ".join(sorted({e.category for e in result.entities}))
                    state.answer = _PII_REFUSAL.format(categories=categories)
                    state.citations = []
                    state.decision = "finalize"
                    state.decisions.append("pii_blocked")
                    state.thought_process.append(
                        {
                            "step": "pii_guard",
                            "attempt": state.current_attempt,
                            "detail": f"Blocked: detected {categories}",
                            "timestamp": _utcnow().isoformat(),
                        }
                    )
                    return True
                if s.pii_mode == "redact":
                    search_query = result.redacted_text

        # HyDE query rewriting.
        if s.workflow_enable_query_rewriting:
            search_query = self.query_rewriter.generate_hyde_search_query(
                user_query=search_query,
                search_history=state.search_history,
                previous_reviews=state.previous_reviews,
            )

        results = self.search_service.search(
            search_query,
            top_k=s.workflow_search_top_k,
            filters=state.filters,
            exclude_ids=list(state.processed_content_ids),
        )
        state.current_results = results
        state.search_history.append(
            {
                "attempt": state.current_attempt,
                "query": search_query,
                "result_count": len(results),
            }
        )
        state.thought_process.append(
            {
                "step": "retrieve",
                "attempt": state.current_attempt,
                "detail": f"Retrieved {len(results)} results",
                "query": search_query,
                "timestamp": _utcnow().isoformat(),
            }
        )
        return False

    def _reflect_step(self, state: AgenticRAGState, max_attempts: int) -> str:
        """Review the current results and decide whether to retry or finalise."""
        s = get_settings()

        if not state.current_results:
            state.decision = "finalize"
            state.decisions.append("finalize")
            state.thought_process.append(
                {
                    "step": "review",
                    "attempt": state.current_attempt,
                    "detail": "No results to review; finalising",
                    "timestamp": _utcnow().isoformat(),
                }
            )
            state.current_results = []
            return "finalize"

        if not s.workflow_enable_reflection:
            # Reflection disabled: accept all current results and finalise.
            state.vetted_results.extend(state.current_results)
            for doc in state.current_results:
                state.processed_content_ids.add(doc.content_id)
            state.decision = "finalize"
            state.decisions.append("finalize")
            state.current_results = []
            return "finalize"

        decision, new_vetted, discarded, llm_decision = self.reflection_agent.review_search_results(
            user_query=state.query,
            current_results=state.current_results,
            vetted_results=state.vetted_results,
            search_history=state.search_history,
            max_attempts=max_attempts,
            current_attempt=state.current_attempt,
        )

        state.vetted_results.extend(new_vetted)
        state.discarded_results.extend(discarded)
        for doc in state.current_results:
            state.processed_content_ids.add(doc.content_id)
        state.previous_reviews.append(decision.thought_process)
        state.decisions.append(decision.decision)
        state.thought_process.append(
            {
                "step": "review",
                "attempt": state.current_attempt,
                "detail": decision.thought_process,
                "decision": decision.decision,
                "llm_decision": llm_decision,
                "vetted_added": len(new_vetted),
                "discarded": len(discarded),
                "timestamp": _utcnow().isoformat(),
            }
        )

        route = "search" if decision.decision == "retry" else "finalize"
        state.decision = route
        state.current_results = []
        return route

    def _answer_step(self, state: AgenticRAGState) -> None:
        """Generate the final cited answer from the vetted results."""
        s = get_settings()

        vetted_formatted = _format_vetted_results(state.vetted_results)
        prompt = AnswerGeneratorPrompts.build_answer_prompt(state.query, vetted_formatted)

        try:
            generated = self.answer_generator.generate_answer(
                query=state.query,
                documents=state.vetted_results,
                generated_answer_prompt=prompt,
                conversation_history=state.chat_history,
            )
            answer_text = generated.answer_text
            citations = generated.citations
        except Exception:  # noqa: BLE001 - return a graceful fallback on generation failure
            logger.exception("Answer generation failed")
            answer_text = (
                "I encountered an error while generating an answer. Please try again."
            )
            citations = []

        # Optional answer redaction.
        if s.pii_active and (s.pii_redact_responses or s.pii_mode == "redact") and answer_text:
            try:
                answer_text = self.pii_service.redact_pii(answer_text)
            except Exception:  # noqa: BLE001
                logger.warning("Answer redaction failed; returning unredacted answer", exc_info=True)

        state.answer = answer_text
        state.citations = citations
        state.decision = "answer"
        state.thought_process.append(
            {
                "step": "response",
                "attempt": state.current_attempt,
                "detail": f"Generated answer with {len(citations)} citations",
                "timestamp": _utcnow().isoformat(),
            }
        )
