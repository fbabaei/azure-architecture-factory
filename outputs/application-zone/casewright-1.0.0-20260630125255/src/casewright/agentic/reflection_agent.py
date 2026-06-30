"""Reflection / review agent for the agentic RAG engine (ported from case-assistant-agent).

Reviews each search iteration's results, separates valid from invalid passages, and decides
whether to retry retrieval or finalise. Includes the "smart retry" override that keeps
retrieving when a result set is only partially relevant.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from casewright.agentic.models import RetrievedDocument, ReviewDecision
from casewright.agentic.prompts import ReflectionAgentPrompts
from casewright.core.clients import get_openai_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)


def _format_results(results: list[RetrievedDocument]) -> str:
    if not results:
        return "(none)"
    blocks = []
    for i, doc in enumerate(results):
        reranker = f"{doc.reranker_score:.3f}" if doc.reranker_score is not None else "n/a"
        blocks.append(
            f"Result #{i}\n"
            f"Content ID: {doc.content_id}\n"
            f"Document ID: {doc.document_id}\n"
            f"Title: {doc.title}\n"
            f"Score: {doc.score:.3f}\n"
            f"Reranker Score: {reranker}\n"
            f"Content: {doc.content[:500]}"
        )
    return "\n\n".join(blocks)


def _format_history(search_history: list[dict[str, Any]]) -> str:
    if not search_history:
        return "(no previous attempts)"
    lines = []
    for h in search_history:
        lines.append(
            f"Attempt #{h.get('attempt', '?')}: query={h.get('query', '')!r}, "
            f"results={h.get('result_count', 0)}"
        )
    return "\n".join(lines)


class ReflectionAgent:
    """Evaluates search results and decides whether to retry or finalise retrieval."""

    def review_search_results(
        self,
        user_query: str,
        current_results: list[RetrievedDocument],
        vetted_results: list[RetrievedDocument],
        search_history: list[dict[str, Any]],
        max_attempts: int,
        current_attempt: int,
    ) -> tuple[ReviewDecision, list[RetrievedDocument], list[RetrievedDocument], str]:
        """Return ``(decision, new_vetted, discarded, llm_original_decision)``."""
        s = get_settings()
        client = get_openai_client()

        current_count = len(current_results)
        prompt = ReflectionAgentPrompts.build_review_prompt(
            user_query=user_query,
            current_results_formatted=_format_results(current_results),
            vetted_results_formatted=_format_results(vetted_results),
            vetted_results_count=len(vetted_results),
            search_history_formatted=_format_history(search_history),
            current_results_count=current_count,
            current_attempt=current_attempt,
            max_attempts=max_attempts,
        )

        try:
            response = client.chat.completions.create(
                model=s.chat_deployment,
                messages=[
                    {"role": "system", "content": ReflectionAgentPrompts.SEARCH_REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            decision = ReviewDecision.model_validate(json.loads(content))
        except Exception:  # noqa: BLE001 - fall back to accept-all + finalize
            logger.warning("Reflection review failed; accepting all results and finalising", exc_info=True)
            decision = ReviewDecision(
                thought_process="Review failed; accepting all results as a fallback.",
                valid_results=list(range(current_count)),
                invalid_results=[],
                decision="finalize",
            )

        llm_original_decision = decision.decision

        # Filter indices to the valid range.
        valid_idx = [i for i in decision.valid_results if 0 <= i < current_count]
        invalid_idx = [i for i in decision.invalid_results if 0 <= i < current_count]

        new_vetted = [current_results[i] for i in valid_idx]
        discarded = [current_results[i] for i in invalid_idx]

        # Smart retry: override "finalize" when results are only partially relevant.
        final_decision = self._apply_smart_retry_logic(
            decision.decision,
            valid_count=len(new_vetted),
            total_count=current_count,
            current_attempt=current_attempt,
            max_attempts=max_attempts,
        )
        decision.decision = final_decision  # type: ignore[assignment]

        return decision, new_vetted, discarded, llm_original_decision

    def _apply_smart_retry_logic(
        self,
        decision: str,
        valid_count: int,
        total_count: int,
        current_attempt: int,
        max_attempts: int,
    ) -> str:
        """Override ``finalize`` → ``retry`` when validity is only moderate and retries remain."""
        s = get_settings()
        if decision != "finalize":
            return decision
        if current_attempt >= max_attempts:
            return "finalize"
        if total_count == 0:
            return decision

        valid_percentage = valid_count / total_count
        high = s.reflection_high_validity_threshold
        moderate = s.reflection_moderate_validity_threshold
        moderate_min = s.reflection_moderate_validity_min_count

        if valid_percentage >= high:
            logger.info(
                "smart-retry: validity %.0f%% >= high threshold; retrying for more coverage",
                valid_percentage * 100,
            )
            return "retry"
        if valid_percentage >= moderate and valid_count >= moderate_min:
            logger.info(
                "smart-retry: validity %.0f%% moderate with %d valid; retrying",
                valid_percentage * 100,
                valid_count,
            )
            return "retry"
        return "finalize"
