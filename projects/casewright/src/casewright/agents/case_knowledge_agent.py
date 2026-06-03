"""The case-knowledge agent.

Two execution paths, selected at runtime from settings:

1. **Foundry hosted agent (primary)** — when FOUNDRY_PROJECT_ENDPOINT + FOUNDRY_AGENT_ID are
   set, the bare question is handed to the hosted agent. Retrieval is owned by the Foundry IQ
   *knowledge base*: the agent calls its ``knowledge_base_retrieve`` MCP tool, which runs
   agentic (LLM-planned) retrieval over the ``casewright-index`` and grounds the answer. The
   app does not pre-retrieve on this path. Citations are read back from the assistant
   message's URL-citation annotations.
2. **Deterministic local fallback** — a direct Azure OpenAI chat completion grounded on the
   in-process hybrid + semantic retrieval. Always available, so the API works in any
   environment with no Foundry project / knowledge base provisioned (offline resilience).
"""
from __future__ import annotations

import logging

from casewright.agents.prompts import SYSTEM_PROMPT
from casewright.core.clients import get_openai_client
from casewright.core.models import Citation, ChatRequest, ChatResponse, ChatTurn
from casewright.core.settings import get_settings
from casewright.retrieval.query import RetrievedPassage, retrieve

logger = logging.getLogger(__name__)


def _format_context(passages: list[RetrievedPassage]) -> str:
    if not passages:
        return "(no relevant case material found)"
    return "\n\n".join(
        f"[{i + 1}] {p.title}\n{p.content}" for i, p in enumerate(passages)
    )


class CaseKnowledgeAgent:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def answer(self, request: ChatRequest, history: list[ChatTurn]) -> ChatResponse:
        if self._settings.foundry_enabled:
            try:
                answer, citations = self._answer_foundry(request, history)
                return ChatResponse(
                    conversation_id=request.conversation_id,
                    answer=answer,
                    citations=citations,
                    runtime="foundry",
                )
            except Exception:  # pragma: no cover - defensive fallback
                logger.exception("Foundry agent failed; falling back to local generation")

        passages = retrieve(request.message)
        answer = self._answer_local(request, history, passages)
        return ChatResponse(
            conversation_id=request.conversation_id,
            answer=answer,
            citations=[p.as_citation() for p in passages],
            runtime="local",
        )

    def _answer_foundry(
        self, request: ChatRequest, history: list[ChatTurn]
    ) -> tuple[str, list[Citation]]:
        """Hand the question to the hosted agent; it retrieves via its KB MCP tool."""
        from azure.ai.projects import AIProjectClient

        from casewright.core.clients import get_credential

        client = AIProjectClient(
            endpoint=self._settings.foundry_project_endpoint,
            credential=get_credential(),
        )
        agents = client.agents
        thread = agents.threads.create()
        agents.messages.create(thread_id=thread.id, role="user", content=request.message)
        run = agents.runs.create_and_process(
            thread_id=thread.id, agent_id=self._settings.foundry_agent_id
        )
        if run.status != "completed":
            raise RuntimeError(f"Foundry run did not complete: {run.status}")
        messages = agents.messages.list(thread_id=thread.id)
        for message in messages:
            if message.role == "assistant" and message.text_messages:
                answer = message.text_messages[-1].text.value
                return answer, _extract_citations(message)
        raise RuntimeError("Foundry run returned no assistant message")

    def _answer_local(
        self, request: ChatRequest, history: list[ChatTurn], passages: list[RetrievedPassage]
    ) -> str:
        client = get_openai_client()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in history[-6:]:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append(
            {
                "role": "user",
                "content": f"Context:\n{_format_context(passages)}\n\nQuestion: {request.message}",
            }
        )
        completion = client.chat.completions.create(
            model=self._settings.chat_deployment,
            messages=messages,
            temperature=0.2,
        )
        return completion.choices[0].message.content or ""


def _extract_citations(message: object) -> list[Citation]:
    """Best-effort read of URL-citation annotations from a hosted-agent message.

    The knowledge base returns grounding references that the Foundry runtime surfaces as
    URL-citation annotations. Shape varies across SDK versions, so this is defensive and
    returns an empty list when annotations are absent.
    """
    annotations = getattr(message, "url_citation_annotations", None) or []
    citations: list[Citation] = []
    for ann in annotations:
        url_citation = getattr(ann, "url_citation", None)
        if url_citation is None:
            continue
        title = getattr(url_citation, "title", None) or ""
        url = getattr(url_citation, "url", None) or ""
        if title or url:
            citations.append(Citation(document_title=title or url, source_path=url, score=0.0))
    return citations
