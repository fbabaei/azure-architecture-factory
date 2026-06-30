"""HyDE query rewriter for the agentic RAG engine (ported from case-assistant-agent)."""
from __future__ import annotations

import json
import logging
from typing import Any

from casewright.agentic.models import RewrittenQuery
from casewright.agentic.prompts import QueryRewriterPrompts
from casewright.core.clients import get_openai_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)


class QueryRewriter:
    """Generates Hypothetical Document Embeddings (HyDE) search queries."""

    def generate_hyde_search_query(
        self,
        user_query: str,
        search_history: list[dict[str, Any]] | None = None,
        previous_reviews: list[str] | None = None,
    ) -> str:
        """Generate a hypothetical passage to embed for retrieval. Falls back to the original query."""
        s = get_settings()
        client = get_openai_client()

        context_parts = [f"User Question: {user_query}"]
        if search_history:
            previous_queries = [h.get("query", "") for h in search_history if h.get("query")]
            if previous_queries:
                context_parts.append(
                    "\nPrevious search queries already attempted (generate something different):\n"
                    + "\n".join(f"- {q}" for q in previous_queries)
                )
                context_parts.append(
                    "\nDiversify: vary terminology, shift perspective, or focus on adjacent aspects."
                )
        if previous_reviews:
            context_parts.append(
                "\nPrevious Review Analysis:\n" + "\n".join(previous_reviews[-2:])
            )

        user_message = "\n".join(context_parts)

        try:
            response = client.chat.completions.create(
                model=s.chat_deployment,
                messages=[
                    {"role": "system", "content": QueryRewriterPrompts.HYDE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=s.workflow_hyde_temperature,
                max_tokens=s.workflow_hyde_max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            rewritten = RewrittenQuery.model_validate(json.loads(content))
            passage = rewritten.hypothetical_passage.strip()
            if passage:
                logger.info("HyDE rewrite produced a hypothetical passage (%d chars)", len(passage))
                return passage
        except Exception:  # noqa: BLE001 - never block retrieval on rewrite failure
            logger.warning("HyDE query rewriting failed; falling back to original query", exc_info=True)

        return user_query
