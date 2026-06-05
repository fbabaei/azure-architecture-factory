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

import base64
import binascii
import logging
import re
from urllib.parse import unquote

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


_MCP_REF_PREFIX = "mcp://searchindex/"
_CHUNK_SUFFIX = re.compile(r"_chunks_\d+$")
# A blob/source URL optionally followed by a single spurious base64-padding digit
# (the chunk key encodes the parent document key and can carry one extra trailing char).
_TRAILING_PAD_DIGIT = re.compile(r"^(https?://\S+?\.[A-Za-z]{2,5})\d*$")


def _decode_mcp_reference(reference: str) -> tuple[str, str]:
    """Map a Foundry knowledge-base MCP citation reference to a (source_path, title) pair.

    The hosted agent returns grounding references such as
    ``mcp://searchindex/<hash>_<base64url(blob_url)>_chunks_<n>``. This recovers the
    original blob URL and a human-friendly filename title. Returns the reference unchanged
    when it is not a recognised MCP reference or cannot be decoded.
    """
    if not reference.startswith(_MCP_REF_PREFIX):
        return reference, reference
    content_id = reference[len(_MCP_REF_PREFIX):]
    content_id = _CHUNK_SUFFIX.sub("", content_id)
    # Drop the leading content hash prefix (everything up to the first underscore).
    _, _, segment = content_id.partition("_")
    if not segment:
        return reference, reference
    padded = segment + "=" * (-len(segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return reference, reference
    match = _TRAILING_PAD_DIGIT.match(decoded)
    source_path = match.group(1) if match else decoded
    title = unquote(source_path.rstrip("/").rsplit("/", 1)[-1]) or source_path
    return source_path, title


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
        """Hand the question to the hosted prompt agent via the OpenAI Responses API.

        The deployed agent is a Foundry V2 *prompt agent*, invoked through the Responses
        protocol with an ``agent_reference`` (not the assistants threads/runs API).
        Retrieval and grounding are owned by the agent's Foundry IQ knowledge-base MCP
        tool; citations are read back from the response output annotations.
        """
        from azure.ai.projects import AIProjectClient

        from casewright.core.clients import get_credential

        client = AIProjectClient(
            endpoint=self._settings.foundry_project_endpoint,
            credential=get_credential(),
        )
        openai_client = client.get_openai_client()
        agent_reference = {
            "name": self._settings.foundry_agent_id,
            "type": "agent_reference",
        }
        input_messages: list[dict[str, str]] = [
            {"role": turn.role, "content": turn.content} for turn in history[-6:]
        ]
        input_messages.append({"role": "user", "content": request.message})
        response = openai_client.responses.create(
            extra_body={"agent_reference": agent_reference},
            input=input_messages,
        )
        answer = response.output_text or ""
        if not answer:
            raise RuntimeError("Foundry agent returned an empty response")
        return answer, _extract_citations(response)

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


def _extract_citations(response: object) -> list[Citation]:
    """Best-effort read of URL-citation annotations from a Responses API result.

    The knowledge base returns grounding references that the Foundry runtime surfaces as
    annotations on the response's output text parts. Shape varies across SDK versions, so
    this is defensive and returns an empty list when annotations are absent.
    """
    citations: list[Citation] = []
    output = getattr(response, "output", None) or []
    for item in output:
        content_parts = getattr(item, "content", None) or []
        for part in content_parts:
            annotations = getattr(part, "annotations", None) or []
            for ann in annotations:
                url = getattr(ann, "url", None) or ""
                title = getattr(ann, "title", None) or ""
                if not (url or title):
                    # Some SDK versions nest under a ``url_citation`` attribute.
                    url_citation = getattr(ann, "url_citation", None)
                    if url_citation is not None:
                        url = getattr(url_citation, "url", None) or ""
                        title = getattr(url_citation, "title", None) or ""
                if not (title or url):
                    continue
                source_path, decoded_title = _decode_mcp_reference(url or title)
                display_title = (
                    title
                    if title and not title.startswith(_MCP_REF_PREFIX)
                    else decoded_title
                )
                citations.append(
                    Citation(
                        document_title=display_title or source_path,
                        source_path=source_path,
                        score=0.0,
                    )
                )
    return citations
