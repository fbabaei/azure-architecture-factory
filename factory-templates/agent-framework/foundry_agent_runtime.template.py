"""Microsoft Agent Framework SDK runtime adapter - factory template.

This module is a factory template. Projects adopting the Agent Framework
runtime should copy this file into ``src/<package>/services/`` as
``foundry_agent_runtime.py`` and replace the PROJECT-SPECIFIC markers
with their own services.

**What this adapter provides**

- A drop-in alternative runtime that wraps the project's existing
  deterministic services with Microsoft Agent Framework SDK ``Agent``
  instances backed by ``FoundryChatClient``.
- A forward-progress safety net for multi-turn clarification loops:
  when the LLM fails to advance the state (no tool call, or the same
  missing-field set before and after), a deterministic helper is
  invoked so the loop always progresses.
- Graceful degradation: the factory entry point (``build_foundry_runtime``)
  raises ``RuntimeError`` if the SDK is not installed or Foundry is not
  configured. Callers should fall back to the deterministic local
  runtime on that error so the service stays online.

**The deterministic-contract rule**

Tool functions MUST delegate all state mutation to pure Python helpers
that already exist in the project. The LLM decides WHICH field / action
to invoke; the helper decides HOW the state changes. This preserves the
project's validation, audit logging, and persistence contract across
both runtimes.

**Env flags (convention)**

- ``AGENT_FRAMEWORK_ENABLED=1`` - opt in to the SDK runtime
- ``FOUNDRY_PROJECT_ENDPOINT`` - full project URL
- ``FOUNDRY_MODEL_DEPLOYMENT_NAME`` - Azure AI Foundry deployment name

The project's ``Settings`` dataclass should expose a derived
``foundry_runtime_enabled`` property that is true only when all three
are populated.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

# ---------------------------------------------------------------------------
# PROJECT-SPECIFIC imports - replace with the project's own modules.
# ---------------------------------------------------------------------------
#
# from ..config import Settings
# from ..models import DomainObject, MANDATORY_FIELDS
# from .agent_runtime import AgentRuntime, LocalChatAgent, LocalExtractionAgent
# from .domain_service import apply_answer_to_domain_object  # deterministic helper
# from .repository import Repository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sync-to-async bridge
# ---------------------------------------------------------------------------


def _run_coro(coro: Awaitable[Any]) -> Any:
    """Run a coroutine from a sync FastAPI handler context.

    FastAPI invokes sync handlers inside a worker thread (no active
    event loop), so ``asyncio.run`` is safe and avoids leaking loops.
    """

    return asyncio.run(coro)


def _extract_agent_text(response: Any) -> str:
    """Best-effort text extraction from an SDK agent response.

    The SDK response shape has evolved across preview releases; this
    helper tolerates the known variants without pinning to a private
    attribute.
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
# Prompts - replace with project-specific instructions.
# ---------------------------------------------------------------------------

_EXTRACTION_INSTRUCTIONS = (
    "You are the <DOMAIN> Extraction Specialist. Given the full text of an "
    "input document, return a single JSON object matching the project's "
    "schema. Return JSON only. Do not wrap in Markdown fences. Never "
    "fabricate values."
)

_CHAT_INSTRUCTIONS = (
    "You are the <DOMAIN> Chat Orchestrator. Answer user questions using "
    "the provided tools. Prefer the knowledge-base tool for general "
    "questions; use the status tool for questions about an existing case. "
    "Never invent facts. Keep answers concise."
)

_CLARIFICATION_INSTRUCTIONS = (
    "You are the <DOMAIN> Clarification Driver. You receive a JSON object "
    "with `session_id`, `user_message`, `missing_fields`, and `current_draft`. "
    "For each missing field you can confidently extract a value for from "
    "the user's message, call `record_clarification_answer` exactly once "
    "with `session_id`, `field`, and the raw string value.\n\n"
    "Rules:\n"
    "- Never call the tool for a field NOT in `missing_fields`.\n"
    "- Never guess. Skip fields the message does not clearly supply.\n"
    "- Pass the user's literal wording; the tool normalises values.\n"
    "- If unsure, apply the first `missing_fields` entry with the raw message.\n"
    "- Do not produce any user-visible text; only emit tool calls."
)


# ---------------------------------------------------------------------------
# Tool builders - replace argument types / helpers with project-specific ones.
# ---------------------------------------------------------------------------


def _build_chat_tools(*, qa_service: Any, repository: Any) -> list[Callable[..., Any]]:
    """Construct async tool callables for the chat orchestrator agent.

    The LLM may call any of these during a chat turn. All tools are
    async-safe and offload sync work with ``asyncio.to_thread`` so the
    FastAPI event loop is not blocked.
    """

    async def answer_knowledge_base_question(question: str) -> str:
        """Answer a general domain question using the knowledge base."""

        answer = await asyncio.to_thread(qa_service.answer, question)
        return answer.answer

    async def fetch_session_status(session_id: str) -> str:
        """Return a JSON snapshot of an existing session's state."""

        state = await asyncio.to_thread(repository.get, session_id)
        if state is None:
            return json.dumps({"session_id": session_id, "exists": False})
        return json.dumps({"session_id": session_id, "exists": True, "state": state.model_dump(mode="json")})

    return [answer_knowledge_base_question, fetch_session_status]


def _build_clarification_tools(*, repository: Any, mandatory_fields: tuple[str, ...], apply_answer: Callable[..., Any]) -> list[Callable[..., Any]]:
    """Construct async tool callables for the clarification driver agent.

    The tools delegate all mutation to the project's deterministic
    ``apply_answer`` helper so the field-merge contract is preserved:
    the LLM only decides WHICH fields to apply, never HOW to transform
    values.
    """

    async def get_clarification_state(session_id: str) -> str:
        state = await asyncio.to_thread(repository.get, session_id)
        if state is None:
            return json.dumps({"session_id": session_id, "exists": False})
        # PROJECT-SPECIFIC: compute missing_fields via the project's helper
        # (e.g. build_clarifications(state)).
        return json.dumps({"session_id": session_id, "exists": True, "state": state.model_dump(mode="json")})

    async def record_clarification_answer(session_id: str, field: str, value: str) -> str:
        if field not in mandatory_fields:
            return json.dumps({"ok": False, "error": f"unsupported_field:{field}"})
        state = await asyncio.to_thread(repository.get, session_id)
        if state is None:
            return json.dumps({"ok": False, "error": "unknown_session"})
        updated = apply_answer(state, field, value)
        await asyncio.to_thread(repository.save, updated, "clarification_applied_by_agent")
        return json.dumps({"ok": True})

    return [get_clarification_state, record_clarification_answer]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_foundry_runtime(*, settings: Any, repository: Any, qa_service: Any, local_runtime: Any) -> Any:
    """Build an agent runtime backed by the Agent Framework SDK.

    Raises :class:`RuntimeError` when the SDK packages cannot be
    imported or when required Foundry settings are missing. Callers
    should wrap this in a try/except and fall back to the deterministic
    local runtime on failure so the service stays online.
    """

    if not getattr(settings, "foundry_runtime_enabled", False):
        raise RuntimeError(
            "Foundry runtime is not enabled (set AGENT_FRAMEWORK_ENABLED=1 "
            "plus FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT_NAME)."
        )

    try:  # Lazy import so missing SDK does not crash the app.
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "Microsoft Agent Framework SDK packages are not installed. "
            "Run scripts/install_agent_framework.ps1 (Windows) or "
            "scripts/install_agent_framework.sh (Linux) to install them."
        ) from exc

    credential = DefaultAzureCredential()
    client = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model_deployment,
        credential=credential,
    )

    # PROJECT-SPECIFIC: instantiate the project's three agents with their
    # own instructions and tool sets. The clarification agent is only
    # needed when the project has a multi-turn clarification loop.
    extraction_agent = Agent(client=client, name="ExtractionSpecialist", instructions=_EXTRACTION_INSTRUCTIONS)
    chat_agent = Agent(
        client=client,
        name="ChatOrchestrator",
        instructions=_CHAT_INSTRUCTIONS,
        tools=_build_chat_tools(qa_service=qa_service, repository=repository),
    )
    # clarification_agent = Agent(
    #     client=client,
    #     name="ClarificationDriver",
    #     instructions=_CLARIFICATION_INSTRUCTIONS,
    #     tools=_build_clarification_tools(
    #         repository=repository,
    #         mandatory_fields=MANDATORY_FIELDS,
    #         apply_answer=apply_answer_to_domain_object,
    #     ),
    # )

    logger.info(
        "Foundry agent runtime initialised (endpoint=%s, model=%s)",
        settings.foundry_project_endpoint,
        settings.foundry_model_deployment,
    )

    return FoundryAgentRuntime(
        extraction_agent=extraction_agent,
        chat_agent=chat_agent,
        clarification_agent=None,  # PROJECT-SPECIFIC: swap in clarification_agent above.
        repository=repository,
        local_runtime=local_runtime,
        mandatory_fields=_resolve_mandatory_fields(settings),
    )


# ---------------------------------------------------------------------------
# Reference runtime - generic shape adopting projects can copy verbatim.
# ---------------------------------------------------------------------------


def _resolve_mandatory_fields(settings: Any) -> tuple[str, ...]:
    """PROJECT-SPECIFIC: override with the project's MANDATORY_FIELDS tuple.

    Default returns an empty tuple so the reference runtime runs even
    for projects that do not have a clarification loop.
    """

    return tuple(getattr(settings, "mandatory_fields", ()) or ())


@dataclass
class FoundryAgentRuntime:
    """Generic SDK-backed runtime.

    This class is a complete reference implementation. Adopters can use
    it as-is for the extraction + chat path and add a clarification
    agent when their project needs one. The forward-progress safety net
    is built in: every clarification turn compares the missing-field set
    before and after the LLM call; if the LLM makes no progress, the
    deterministic local runtime owns the step.
    """

    extraction_agent: Any
    chat_agent: Any
    clarification_agent: Any
    repository: Any
    local_runtime: Any
    mandatory_fields: tuple[str, ...] = ()

    # -- Extraction --------------------------------------------------------

    def extract_document(self, text: str) -> dict[str, Any]:
        """Run extraction via the SDK agent, fall back to local on failure."""

        try:
            response = _run_coro(self.extraction_agent.run(text))
            raw = _extract_agent_text(response)
            return json.loads(raw) if raw else {}
        except Exception as exc:
            logger.warning("Extraction agent failed, using local runtime: %s", exc)
            return self.local_runtime.extract_document(text)

    # -- Chat --------------------------------------------------------------

    def respond(self, user_message: str, session_id: str | None = None) -> str:
        """Run a single chat turn via the SDK agent, fall back to local."""

        try:
            prompt = json.dumps({"session_id": session_id, "user_message": user_message})
            response = _run_coro(self.chat_agent.run(prompt))
            text = _extract_agent_text(response)
            if text:
                return text
        except Exception as exc:
            logger.warning("Chat agent failed, using local runtime: %s", exc)
        return self.local_runtime.respond(user_message, session_id=session_id)

    # -- Clarification (multi-turn forward-progress) -----------------------

    def continue_clarification(self, session_id: str, user_message: str) -> dict[str, Any]:
        """Advance a clarification loop by exactly one step.

        Implements rule 3 of the pattern: compute the missing-field set
        before the LLM call, run the SDK agent (which delegates mutation
        to ``record_clarification_answer``), compute the set again, and
        if it did not shrink, ask the local runtime to apply a
        deterministic step so the loop always progresses.
        """

        pre_missing = self._missing_fields(session_id)

        if self.clarification_agent is None:
            return self.local_runtime.continue_clarification(session_id, user_message)

        try:
            prompt = json.dumps(
                {
                    "session_id": session_id,
                    "user_message": user_message,
                    "missing_fields": pre_missing,
                }
            )
            _run_coro(self.clarification_agent.run(prompt))
        except Exception as exc:
            logger.warning("Clarification agent failed, using local step: %s", exc)
            return self.local_runtime.continue_clarification(session_id, user_message)

        post_missing = self._missing_fields(session_id)
        if set(post_missing) >= set(pre_missing):
            # No progress. Fire the deterministic safety net.
            logger.info(
                "Clarification agent made no progress on %s; applying local step",
                session_id,
            )
            return self.local_runtime.continue_clarification(session_id, user_message)

        return {"session_id": session_id, "missing_fields": post_missing, "advanced_by": "agent-framework"}

    # -- Internal helpers --------------------------------------------------

    def _missing_fields(self, session_id: str) -> list[str]:
        """PROJECT-SPECIFIC: compute missing fields from repository state.

        Default implementation returns an empty list so the runtime is
        usable even before the project wires its own helper.
        """

        state = self.repository.get(session_id)
        if state is None:
            return list(self.mandatory_fields)
        present = {field for field in self.mandatory_fields if getattr(state, field, None)}
        return [field for field in self.mandatory_fields if field not in present]
