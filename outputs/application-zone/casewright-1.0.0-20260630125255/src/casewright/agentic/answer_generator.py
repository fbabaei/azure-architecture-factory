"""Answer generator for the agentic RAG engine (ported from case-assistant-agent).

Generates a grounded answer where the LLM emits ``{content_id}`` citation markers, then
rewrites those markers to sequential ``[n]`` indices ordered by first appearance and builds the
matching ``Citation`` list. Unmatched markers are stripped and consecutive citations are sorted.
"""
from __future__ import annotations

import logging
import re

from casewright.agentic.citation_tracker import CitationTracker
from casewright.agentic.models import Citation, GeneratedAnswer, RetrievedDocument
from casewright.agentic.prompts import AnswerGeneratorPrompts
from casewright.core.clients import get_openai_client
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\{([^}]+)\}")
_CITATION_NUMBER_PATTERN = re.compile(r"\[(\d+)\]")
_CONSECUTIVE_CITATIONS_PATTERN = re.compile(r"(?:\[\d+\]){2,}")

_FALLBACK_ANSWER = (
    "I couldn't find relevant information in the content documents to answer your question. "
    "This may be due to applied filters limiting available results. Please try rephrasing your "
    "question, adjusting your filters, or check if the information exists in the uploaded documents."
)


class AnswerGenerator:
    """Generates cited answers from vetted documents."""

    def __init__(self, citation_tracker: CitationTracker) -> None:
        self._citation_tracker = citation_tracker

    def generate_answer(
        self,
        query: str,
        documents: list[RetrievedDocument],
        generated_answer_prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> GeneratedAnswer:
        """Generate an answer with inline ``[n]`` citations for the supplied documents."""
        if not documents:
            return self._generate_fallback_answer()

        raw_answer = self._call_llm(generated_answer_prompt, conversation_history)

        cited_docs = self._extract_cited_documents(raw_answer, documents)
        final_text = self._replace_content_with_indices(raw_answer, cited_docs)
        citations = self._citation_tracker.create_citations(cited_docs)

        return GeneratedAnswer(
            answer_text=final_text,
            citations=citations,
            metadata={"document_count": len(documents), "cited_count": len(cited_docs)},
        )

    def _call_llm(self, prompt: str, conversation_history: list[dict[str, str]] | None) -> str:
        s = get_settings()
        client = get_openai_client()

        messages: list[dict[str, str]] = [
            {"role": "system", "content": AnswerGeneratorPrompts.ANSWER_GENERATOR_SYSTEM_PROMPT}
        ]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=s.chat_deployment,
            messages=messages,
            temperature=s.workflow_answer_temperature,
            max_tokens=s.workflow_answer_max_tokens,
        )
        return response.choices[0].message.content or ""

    def _generate_fallback_answer(self) -> GeneratedAnswer:
        return GeneratedAnswer(answer_text=_FALLBACK_ANSWER, citations=[], metadata={"fallback": True})

    def _extract_cited_documents(
        self, answer: str, documents: list[RetrievedDocument]
    ) -> list[RetrievedDocument]:
        """Return cited documents in order of first appearance of their ``{content_id}`` marker."""
        by_content_id = {doc.content_id: doc for doc in documents}
        ordered: list[RetrievedDocument] = []
        seen: set[str] = set()
        for match in _CITATION_PATTERN.finditer(answer):
            content_id = match.group(1).strip()
            if content_id in by_content_id and content_id not in seen:
                seen.add(content_id)
                ordered.append(by_content_id[content_id])
        return ordered

    def _replace_content_with_indices(
        self, answer: str, cited_docs: list[RetrievedDocument]
    ) -> str:
        """Replace ``{content_id}`` markers with ``[n]`` indices; drop unmatched markers."""
        index_by_content_id = {doc.content_id: i + 1 for i, doc in enumerate(cited_docs)}

        def _sub(match: re.Match[str]) -> str:
            content_id = match.group(1).strip()
            idx = index_by_content_id.get(content_id)
            return f"[{idx}]" if idx is not None else ""

        text = _CITATION_PATTERN.sub(_sub, answer)
        # Clean up whitespace left by removed markers.
        text = re.sub(r"\s+([.,;:])", r"\1", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = self._sort_consecutive_citations(text)
        return text.strip()

    def _sort_consecutive_citations(self, text: str) -> str:
        """Sort runs of consecutive citations, e.g. ``[2][1]`` → ``[1][2]``."""

        def _sort(match: re.Match[str]) -> str:
            numbers = _CITATION_NUMBER_PATTERN.findall(match.group(0))
            unique_sorted = sorted({int(n) for n in numbers})
            return "".join(f"[{n}]" for n in unique_sorted)

        return _CONSECUTIVE_CITATIONS_PATTERN.sub(_sort, text)
