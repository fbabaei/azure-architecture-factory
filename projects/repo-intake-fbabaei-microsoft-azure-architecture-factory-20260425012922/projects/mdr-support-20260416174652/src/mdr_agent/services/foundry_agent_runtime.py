"""Microsoft Agent Framework SDK-backed runtime for the MDR application.

Mirrors the deterministic runtime in ``agent_runtime.py`` but wires the
Chat Orchestrator and Extraction Specialist to real ``agent_framework``
``Agent`` instances backed by ``FoundryChatClient``.

Deterministic Python services (ingestion, extraction JSON parsing,
repository persistence, QA retrieval, clarification loop) are surfaced
as tool functions so the LLM agents can call them via the SDK's
function-calling contract.

The SDK packages are preview (``agent-framework-core==1.0.0rc6`` and
``azure-ai-agentserver-*==1.0.0b16``) and must be installed out-of-band.
This module imports them lazily inside :func:`build_foundry_runtime` so
the application can still start on hosts where the SDK is not present.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from ..config import Settings
from ..models import (
    ApiChatResponse,
    ChatResponse,
    ChatTurn,
    ClarificationBundle,
    ExtractionResult,
    MANDATORY_FIELDS,
    MDRArrangement,
)
from .agent_runtime import (
    AgentRuntime,
    ChatOrchestratorAgent as LocalChatOrchestratorAgent,
    ExtractionSpecialistAgent as LocalExtractionSpecialistAgent,
)
from .chat_session import apply_answer_to_arrangement, handle_chat_turn
from .clarification_service import build_clarifications
from .document_ingestion import DocumentIngestionService
from .extraction_agent import (
    CONFIDENCE_SCORES,
    ExtractionAgent,
    ExtractionError,
    ExtractionOutcome,
)
from .guardrails import is_off_topic, off_topic_reply
from .qa_service import QAService
from .repository import ArrangementRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_coro(coro: Awaitable[Any]) -> Any:
    """Run a coroutine from a sync FastAPI handler context.

    FastAPI invokes sync handlers inside a worker thread (no active
    event loop), so ``asyncio.run`` is safe and avoids leaking loops.
    """

    return asyncio.run(coro)


def _parse_extraction_text(raw: str, fallback_model: str) -> ExtractionOutcome:
    """Parse the extraction-agent JSON response into an ``ExtractionOutcome``."""

    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            "Extraction agent returned non-JSON output"
        ) from exc

    arrangement_payload = payload.get("arrangement")
    if not isinstance(arrangement_payload, dict):
        raise ExtractionError(
            "Extraction agent response missing 'arrangement' object"
        )
    try:
        arrangement = MDRArrangement.model_validate(arrangement_payload)
    except Exception as exc:  # pragma: no cover - validation error path
        raise ExtractionError(
            f"Extraction agent response failed schema validation: {exc}"
        ) from exc

    label = str(payload.get("confidence_label") or "low").lower()
    if label not in CONFIDENCE_SCORES:
        label = "low"
    confidence = CONFIDENCE_SCORES[label]  # type: ignore[index]
    return ExtractionOutcome(
        arrangement=arrangement,
        confidence=confidence,
        confidence_label=label,  # type: ignore[arg-type]
        model=fallback_model,
    )


# ---------------------------------------------------------------------------
# Foundry agent wrappers
# ---------------------------------------------------------------------------


@dataclass
class FoundryExtractionSpecialistAgent:
    """SDK-backed extraction agent.

    The SDK ``Agent`` is prompted with the document text and must return
    a JSON payload matching :class:`MDRArrangement`. Persistence and
    audit logging keep using the existing repository service.
    """

    agent: Any
    ingestion: DocumentIngestionService
    repository: ArrangementRepository
    model_deployment: str
    local_fallback: LocalExtractionSpecialistAgent
    clarification_agent: Any = None

    def extract_document(
        self,
        *,
        arrangement_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        reference: str | None = None,
    ) -> ExtractionResult:
        ingested = self.ingestion.ingest(
            arrangement_id=arrangement_id,
            filename=filename,
            content_type=content_type,
            data=data,
        )
        outcome = self._run_extraction(ingested.text)
        arrangement = outcome.arrangement
        arrangement.arrangement_id = arrangement_id
        if reference and not arrangement.reference:
            arrangement.reference = reference
        self.repository.save(arrangement, reason="upload_extracted")
        self.repository.record_event(
            arrangement_id,
            "document_ingested",
            details={
                "content_type": content_type,
                "filename": filename,
                "source_pages": ingested.page_count,
                "runtime": "foundry",
            },
        )
        return ExtractionResult(
            arrangement_id=arrangement_id,
            arrangement=arrangement,
            confidence=outcome.confidence,
            confidence_label=outcome.confidence_label,
            source_pages=ingested.page_count,
            extraction_model=outcome.model,
        )

    def extract_text(
        self,
        *,
        arrangement_id: str,
        text: str,
        reference: str | None = None,
    ) -> ExtractionResult:
        outcome = self._run_extraction(text)
        arrangement = outcome.arrangement
        arrangement.arrangement_id = arrangement_id
        if reference and not arrangement.reference:
            arrangement.reference = reference
        self.repository.save(arrangement, reason="text_draft_created")
        self.repository.record_event(
            arrangement_id,
            "text_draft_created",
            details={"character_count": len(text), "runtime": "foundry"},
        )
        return ExtractionResult(
            arrangement_id=arrangement_id,
            arrangement=arrangement,
            confidence=outcome.confidence,
            confidence_label=outcome.confidence_label,
            source_pages=1,
            extraction_model=outcome.model,
        )

    def continue_clarification(
        self, *, arrangement_id: str, user_message: str
    ) -> ChatResponse:
        """Drive a clarification turn through the SDK clarification Agent.

        The LLM parses the user's message and calls
        ``record_clarification_answer`` once per field it can confidently
        extract. The tool invokes the deterministic merge helper, so the
        field-mutation contract stays identical to the legacy state
        machine. If the LLM fails to make forward progress (or the SDK
        call raises), we fall back to the deterministic single-field
        merge to guarantee the clarification loop always advances.
        """

        arrangement = self.repository.get(arrangement_id)
        if arrangement is None:
            raise ValueError(f"Unknown arrangement_id: {arrangement_id}")

        self.repository.append_turn(
            arrangement_id,
            ChatTurn(
                role="user",
                content=user_message,
                timestamp=datetime.now(timezone.utc),
            ),
        )

        pre_bundle = build_clarifications(arrangement)

        llm_driven = False
        if self.clarification_agent is not None and not pre_bundle.is_complete:
            try:
                _run_coro(
                    self._invoke_clarification_agent(
                        arrangement_id=arrangement_id,
                        user_message=user_message,
                        pre_bundle=pre_bundle,
                        arrangement=arrangement,
                    )
                )
                llm_driven = True
            except Exception as exc:  # pragma: no cover - runtime safety net
                logger.warning(
                    "Foundry clarification agent failed, falling back to deterministic merge: %s",
                    exc,
                )

        # Tools may have mutated state through the repository.
        arrangement = self.repository.get(arrangement_id) or arrangement
        arrangement.arrangement_id = arrangement_id
        post_bundle = build_clarifications(arrangement)

        # Safety net: if the LLM made no progress, apply the
        # deterministic single-field merge so the loop always advances.
        if (
            not pre_bundle.is_complete
            and set(post_bundle.missing_fields) == set(pre_bundle.missing_fields)
        ):
            field_name = pre_bundle.missing_fields[0]
            arrangement = apply_answer_to_arrangement(
                arrangement, field_name, user_message
            )
            arrangement.arrangement_id = arrangement_id
            self.repository.save(
                arrangement,
                reason=(
                    "clarification_applied_fallback"
                    if llm_driven
                    else "clarification_applied"
                ),
            )
            post_bundle = build_clarifications(arrangement)

        if post_bundle.is_complete:
            reply = (
                "Thanks — I have everything I need. You can now generate the arrangement draft."
            )
        else:
            next_q = post_bundle.questions[0]
            reply = next_q.question + (
                f" ({next_q.hint})" if next_q.hint else ""
            )

        self.repository.append_turn(
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

    async def _invoke_clarification_agent(
        self,
        *,
        arrangement_id: str,
        user_message: str,
        pre_bundle: ClarificationBundle,
        arrangement: MDRArrangement,
    ) -> None:
        prompt = json.dumps(
            {
                "session_id": arrangement_id,
                "user_message": user_message,
                "missing_fields": list(pre_bundle.missing_fields),
                "current_draft": arrangement.model_dump(mode="json"),
            }
        )
        # Fire-and-discard: the Agent calls tools that mutate state via
        # the repository. Its free-text response is not surfaced to the
        # user (the deterministic state machine composes the reply).
        await self.clarification_agent.run(prompt)

    # ------------------------------------------------------------------
    def _run_extraction(self, text: str) -> ExtractionOutcome:
        try:
            raw = _run_coro(self._invoke_agent(text))
        except ExtractionError:
            raise
        except Exception as exc:  # pragma: no cover - runtime safety net
            logger.warning(
                "Foundry extraction agent failed, falling back to local agent: %s",
                exc,
            )
            # Route the failure to the local deterministic extractor so a
            # transient Foundry outage does not take the app offline.
            return self.local_fallback.extractor.extract(text)
        return _parse_extraction_text(raw, fallback_model=self.model_deployment)

    async def _invoke_agent(self, text: str) -> str:
        response = await self.agent.run(text)
        return _extract_agent_text(response)


@dataclass
class FoundryChatOrchestratorAgent:
    """SDK-backed chat orchestrator.

    Exposes three tool functions to the LLM: ``answer_mdr_question``,
    ``continue_clarification``, and ``fetch_arrangement_status``. The
    agent decides which tool to invoke based on the turn context, and
    this wrapper normalises the resulting output into
    :class:`ApiChatResponse`.
    """

    agent: Any
    repository: ArrangementRepository
    qa_service: QAService
    local_fallback: LocalChatOrchestratorAgent
    extraction_specialist: Any = None

    def respond(self, *, session_id: str, message: str) -> ApiChatResponse:
        user_message = (message or "").strip()
        if is_off_topic(user_message):
            return ApiChatResponse(
                session_id=session_id,
                mode="off_topic",
                reply=off_topic_reply(),
                arrangement=self.repository.get(session_id),
            )

        arrangement = self.repository.get(session_id)

        # Clarification continuations are driven by the SDK
        # ``FoundryExtractionSpecialistAgent`` when available so the
        # LLM can extract multiple fields from a single user turn
        # through the ``record_clarification_answer`` tool. The helper
        # still enforces the deterministic merge contract and falls
        # back to the single-field state machine when the LLM makes no
        # progress.
        if arrangement is not None:
            if self.extraction_specialist is not None:
                response = self.extraction_specialist.continue_clarification(
                    arrangement_id=session_id,
                    user_message=user_message,
                )
            else:
                response = handle_chat_turn(
                    arrangement_id=session_id,
                    user_message=user_message,
                    repository=self.repository,
                )
            return ApiChatResponse(
                session_id=session_id,
                mode="clarification",
                reply=response.reply,
                arrangement=response.arrangement,
                clarifications=response.clarifications,
            )

        try:
            raw = _run_coro(self._invoke_agent(user_message))
        except Exception as exc:  # pragma: no cover - runtime safety net
            logger.warning(
                "Foundry chat agent failed, falling back to local runtime: %s",
                exc,
            )
            return self.local_fallback.respond(
                session_id=session_id, message=user_message
            )

        self.repository.record_event(
            session_id,
            "qa_answered",
            details={"runtime": "foundry"},
        )
        return ApiChatResponse(
            session_id=session_id,
            mode="qa",
            reply=raw,
            arrangement=None,
        )

    async def _invoke_agent(self, message: str) -> str:
        response = await self.agent.run(message)
        return _extract_agent_text(response)


def _extract_agent_text(response: Any) -> str:
    """Best-effort extraction of text content from an SDK agent response.

    The SDK response shape has evolved across preview releases; this
    helper tolerates the known variants without pinning to a single
    private attribute.
    """

    if response is None:
        return ""
    for attr in ("output_text", "text", "content"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    messages = getattr(response, "messages", None)
    if isinstance(messages, list) and messages:
        last = messages[-1]
        text = getattr(last, "text", None) or getattr(last, "content", None)
        if isinstance(text, str):
            return text
    return str(response)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


_EXTRACTION_INSTRUCTIONS = (
    "You are the MDR (Mandatory Disclosure Rules) Extraction Specialist Agent "
    "for the EY Tax team. When given the full text of a tax arrangement "
    "document you MUST return a single JSON object of the form:\n"
    "{\n"
    '  "arrangement": { "reference": str|null, "summary": str|null, '
    '"implementation_date": ISO-8601|null, "value": number|null, '
    '"currency": str|null, "main_benefit_test": bool|null, '
    '"hallmarks": [...], "parties": [...], "jurisdictions": [...] },\n'
    '  "confidence_label": "low"|"medium"|"high"\n'
    "}\n"
    "Return JSON only. Do not wrap in Markdown fences. Never fabricate "
    "references, TINs, hallmark codes, or jurisdictions."
)


_CHAT_INSTRUCTIONS = (
    "You are the MDR Chat Orchestrator Agent for the EY Tax team. "
    "For every user turn without an active arrangement draft, produce a "
    "concise MDR/DAC6 answer grounded in the knowledge base. Prefer the "
    "`answer_mdr_question` tool so retrieval context is considered. "
    "Use `fetch_arrangement_status` when the user asks about an existing "
    "case. Never invent case law, TINs, or client data. Keep answers "
    "under six sentences and cite hallmark or rule categories when "
    "relevant."
)


_CLARIFICATION_INSTRUCTIONS = (
    "You are the MDR Clarification Driver for the EY Tax team. You receive "
    "a JSON object containing `session_id`, the user's latest `user_message`, "
    "the list of currently `missing_fields`, and the `current_draft`.\n\n"
    "Your job: parse the user's message and, for each missing field you can "
    "confidently extract a value for, call the `record_clarification_answer` "
    "tool exactly once with `session_id`, `field`, and the raw string value. "
    "Supported field names: reference, summary, implementation_date, "
    "hallmarks, parties, jurisdictions.\n\n"
    "Rules:\n"
    "- Never call the tool for a field that is NOT in `missing_fields`.\n"
    "- Never guess. If the message does not clearly supply a value for a "
    "field, skip that field.\n"
    "- Pass the user's literal wording for list fields (hallmarks, parties, "
    "jurisdictions); the tool handles comma/semicolon splitting.\n"
    "- Normalise dates to YYYY-MM-DD when the user provides a date.\n"
    "- If you are unsure which field a short answer refers to, call "
    "`record_clarification_answer` for the first entry in `missing_fields` "
    "using the raw user message.\n"
    "- Do not produce any user-visible text; only emit tool calls."
)


def _build_chat_tools(
    *,
    qa_service: QAService,
    repository: ArrangementRepository,
) -> list[Callable[..., Any]]:
    """Construct async tool callables for the chat orchestrator agent."""

    async def answer_mdr_question(question: str) -> str:
        """Answer a general MDR / DAC6 question using the knowledge base."""

        answer = await asyncio.to_thread(qa_service.answer, question)
        return answer.answer

    async def fetch_arrangement_status(session_id: str) -> str:
        """Return a summary of an existing arrangement draft's clarification state."""

        arrangement = await asyncio.to_thread(repository.get, session_id)
        if arrangement is None:
            return json.dumps({"session_id": session_id, "exists": False})
        bundle = build_clarifications(arrangement)
        return json.dumps(
            {
                "session_id": session_id,
                "exists": True,
                "is_complete": bundle.is_complete,
                "missing_fields": list(bundle.missing_fields),
                "reference": arrangement.reference,
            }
        )

    return [answer_mdr_question, fetch_arrangement_status]


def _build_clarification_tools(
    *,
    repository: ArrangementRepository,
) -> list[Callable[..., Any]]:
    """Construct async tool callables for the clarification driver agent.

    The tools delegate all mutation to :func:`apply_answer_to_arrangement`
    so the deterministic field-merge contract is preserved: the LLM
    only decides WHICH fields to apply, never HOW to transform values.
    """

    async def get_clarification_state(session_id: str) -> str:
        """Return JSON describing the current draft and missing fields."""

        arrangement = await asyncio.to_thread(repository.get, session_id)
        if arrangement is None:
            return json.dumps({"session_id": session_id, "exists": False})
        bundle = build_clarifications(arrangement)
        return json.dumps(
            {
                "session_id": session_id,
                "exists": True,
                "is_complete": bundle.is_complete,
                "missing_fields": list(bundle.missing_fields),
                "current_draft": arrangement.model_dump(mode="json"),
            }
        )

    async def record_clarification_answer(
        session_id: str, field: str, value: str
    ) -> str:
        """Apply a single clarification answer to the named missing field.

        Returns a JSON status object. The call is rejected when the
        field is not one of :data:`MANDATORY_FIELDS`, when the session
        is unknown, or when the field is already populated — this keeps
        the LLM from re-writing fields the analyst already confirmed.
        """

        if field not in MANDATORY_FIELDS:
            return json.dumps(
                {"ok": False, "error": f"unsupported_field:{field}"}
            )
        arrangement = await asyncio.to_thread(repository.get, session_id)
        if arrangement is None:
            return json.dumps({"ok": False, "error": "unknown_session"})

        pre_bundle = build_clarifications(arrangement)
        if field not in pre_bundle.missing_fields:
            return json.dumps(
                {
                    "ok": False,
                    "error": f"field_already_populated:{field}",
                }
            )

        updated = apply_answer_to_arrangement(arrangement, field, value)
        updated.arrangement_id = session_id
        await asyncio.to_thread(
            repository.save,
            updated,
            "clarification_applied_by_agent",
        )
        post_bundle = build_clarifications(updated)
        return json.dumps(
            {
                "ok": True,
                "is_complete": post_bundle.is_complete,
                "missing_fields": list(post_bundle.missing_fields),
            }
        )

    return [get_clarification_state, record_clarification_answer]


def build_foundry_runtime(
    *,
    ingestion: DocumentIngestionService,
    extractor: ExtractionAgent,
    repository: ArrangementRepository,
    qa_service: QAService,
    settings: Settings,
    local_runtime: AgentRuntime,
) -> AgentRuntime:
    """Build an :class:`AgentRuntime` backed by the Agent Framework SDK.

    Raises :class:`RuntimeError` when the SDK packages cannot be
    imported or when required Foundry settings are missing. Callers
    should fall back to the local deterministic runtime in that case.
    """

    if not settings.foundry_runtime_enabled:
        raise RuntimeError(
            "Foundry runtime is not enabled (set AGENT_FRAMEWORK_ENABLED=1 "
            "plus FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT_NAME)."
        )

    try:  # pragma: no cover - exercised only when SDK is installed
        from agent_framework import Agent  # type: ignore[import-not-found]
        from agent_framework.foundry import (  # type: ignore[import-not-found]
            FoundryChatClient,
        )
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "Microsoft Agent Framework SDK packages are not installed. "
            "Install agent-framework-core==1.0.0rc6 and "
            "agent-framework-foundry==1.0.0rc6 (plus azure-identity) "
            "to enable the Foundry runtime."
        ) from exc

    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model_deployment,
        credential=credential,
    )

    extraction_sdk_agent = Agent(
        client=client,
        name="MDRExtractionSpecialist",
        instructions=_EXTRACTION_INSTRUCTIONS,
    )
    clarification_sdk_agent = Agent(
        client=client,
        name="MDRClarificationDriver",
        instructions=_CLARIFICATION_INSTRUCTIONS,
        tools=_build_clarification_tools(repository=repository),
    )
    chat_sdk_agent = Agent(
        client=client,
        name="MDRChatOrchestrator",
        instructions=_CHAT_INSTRUCTIONS,
        tools=_build_chat_tools(
            qa_service=qa_service,
            repository=repository,
        ),
    )

    extraction_wrapper = FoundryExtractionSpecialistAgent(
        agent=extraction_sdk_agent,
        ingestion=ingestion,
        repository=repository,
        model_deployment=settings.foundry_model_deployment,
        local_fallback=local_runtime.extraction_agent,  # type: ignore[arg-type]
        clarification_agent=clarification_sdk_agent,
    )
    chat_wrapper = FoundryChatOrchestratorAgent(
        agent=chat_sdk_agent,
        repository=repository,
        qa_service=qa_service,
        local_fallback=local_runtime.chat_agent,  # type: ignore[arg-type]
        extraction_specialist=extraction_wrapper,
    )
    logger.info(
        "Foundry agent runtime initialised (endpoint=%s, model=%s)",
        settings.foundry_project_endpoint,
        settings.foundry_model_deployment,
    )
    return AgentRuntime(
        chat_agent=chat_wrapper,  # type: ignore[arg-type]
        extraction_agent=extraction_wrapper,  # type: ignore[arg-type]
    )
