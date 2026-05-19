"""Project classifier - deterministic + SDK runtimes.

This module embodies the Agent Framework runtime pattern at the factory
level. The same ``build_classifier`` factory an adopting project would
write to pick its runtime is what the factory itself uses to decide
which runtime a generated project should ship.

Every SDK tool function delegates to the deterministic classifier
(:func:`score_brd`) so the LLM runtime can never produce a
recommendation the local runtime could not produce. The LLM only
decides whether a signal is present; the deterministic helper decides
the final verdict.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .settings import FactorySettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal detection (pure Python, deterministic)
# ---------------------------------------------------------------------------

# Signals that justify shipping the Agent Framework SDK runtime.
_LLM_SIGNALS: tuple[tuple[str, str], ...] = (
    ("foundry", "Azure AI Foundry integration"),
    ("azure openai", "Azure OpenAI integration"),
    ("copilot", "Copilot-style experience"),
    ("chat agent", "conversational agent"),
    ("chat interface", "conversational agent"),
    ("chatbot", "conversational agent"),
    ("llm", "large language model usage"),
    ("large language model", "large language model usage"),
    ("prompt", "prompt-based reasoning"),
    ("retrieval-augmented", "RAG pipeline"),
    (" rag ", "RAG pipeline"),
    ("document extraction", "document extraction"),
    ("information extraction", "information extraction"),
    ("clarification", "multi-turn clarification loop"),
    ("form filling", "form-filling dialog"),
    ("form-filling", "form-filling dialog"),
    ("natural language", "natural language understanding"),
    ("summariz", "summarisation workload"),
    ("classif", "LLM-based classification"),
    ("semantic search", "semantic search"),
    ("vector search", "vector search"),
    ("embedding", "embeddings pipeline"),
)

# Signals that argue AGAINST the SDK runtime (pure ETL / infra / reporting).
_NON_LLM_SIGNALS: tuple[tuple[str, str], ...] = (
    ("etl pipeline", "pure ETL workload"),
    ("batch job", "batch processing"),
    ("data warehouse", "data warehouse loader"),
    ("power bi", "BI reporting"),
    ("infrastructure automation", "infra automation only"),
    ("terraform only", "infra automation only"),
)


@dataclass
class ClassificationResult:
    """Structured outcome of a BRD classification.

    ``runtime`` is the recommendation fed to the orchestrator. ``signals``
    and ``counter_signals`` are the evidence; ``source`` records which
    classifier produced the result (``local`` or ``agent-framework``).
    """

    runtime: str  # "local" | "agent-framework"
    score: int
    signals: list[str] = field(default_factory=list)
    counter_signals: list[str] = field(default_factory=list)
    source: str = "local"
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_brd(brd_text: str) -> ClassificationResult:
    """Deterministic keyword scorer.

    Runs over the BRD text, collects positive and negative signals, and
    emits a :class:`ClassificationResult`. This is the floor the SDK
    classifier must delegate to for its final verdict.
    """

    lowered = (brd_text or "").lower()
    signals: list[str] = []
    for needle, label in _LLM_SIGNALS:
        if needle in lowered and label not in signals:
            signals.append(label)

    counter: list[str] = []
    for needle, label in _NON_LLM_SIGNALS:
        if needle in lowered and label not in counter:
            counter.append(label)

    score = len(signals) - len(counter)
    runtime = "agent-framework" if score >= 1 else "local"
    if runtime == "agent-framework":
        reasoning = (
            "Detected "
            + ", ".join(signals[:3])
            + (" and more" if len(signals) > 3 else "")
            + " \u2014 recommending the Agent Framework SDK runtime alongside "
            "the deterministic fallback."
        )
    else:
        reasoning = (
            "No LLM-driven components detected in the BRD. "
            "The deterministic Python runtime is sufficient; "
            "shipping the SDK would add a preview dependency without benefit."
        )
    return ClassificationResult(
        runtime=runtime,
        score=score,
        signals=signals,
        counter_signals=counter,
        source="local",
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Protocol + runtimes
# ---------------------------------------------------------------------------


class ProjectClassifier(Protocol):
    def classify(self, brd_text: str) -> ClassificationResult: ...


@dataclass
class LocalProjectClassifier:
    """Deterministic classifier. Always available."""

    def classify(self, brd_text: str) -> ClassificationResult:
        return score_brd(brd_text)


@dataclass
class FoundryProjectClassifier:
    """SDK-backed classifier that delegates verdict to the local scorer.

    The LLM is used to *surface* additional signals the deterministic
    scorer may have missed (paraphrases, domain-specific synonyms).
    Those signals are recorded as free-text reasoning, but the final
    verdict still comes from :func:`score_brd` so the two runtimes can
    never disagree on what counts as an LLM workload.
    """

    agent: Any
    local: LocalProjectClassifier

    def classify(self, brd_text: str) -> ClassificationResult:
        # Deterministic floor first - this is what the SDK runtime
        # builds on, exactly like adopting projects must do.
        base = self.local.classify(brd_text)
        try:
            enrichment = asyncio.run(self._invoke_agent(brd_text, base))
        except Exception as exc:  # pragma: no cover - runtime safety net
            logger.warning(
                "Foundry project classifier failed, returning local verdict: %s",
                exc,
            )
            return base

        if not enrichment:
            return base

        merged_signals = list(base.signals)
        for item in enrichment:
            if item not in merged_signals:
                merged_signals.append(item)

        # Forward-progress safety net: if the LLM added no new signal,
        # the SDK runtime returns the deterministic verdict verbatim.
        if merged_signals == base.signals:
            return base

        return ClassificationResult(
            runtime=base.runtime,
            score=base.score,
            signals=merged_signals,
            counter_signals=base.counter_signals,
            source="agent-framework",
            reasoning=(
                base.reasoning
                + " Additional signals surfaced by the Agent Framework classifier: "
                + ", ".join(item for item in merged_signals if item not in base.signals)
                + "."
            ),
        )

    async def _invoke_agent(
        self, brd_text: str, base: ClassificationResult
    ) -> list[str]:
        prompt = json.dumps(
            {
                "brd_text": brd_text[:8000],
                "already_detected": base.signals,
                "deterministic_verdict": base.runtime,
            }
        )
        response = await self.agent.run(prompt)
        text = _extract_agent_text(response)
        if not text:
            return []
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return []
        extra = payload.get("additional_signals")
        if not isinstance(extra, list):
            return []
        return [str(item) for item in extra if isinstance(item, str)]


def _extract_agent_text(response: Any) -> str:
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


_CLASSIFIER_INSTRUCTIONS = (
    "You inspect BRD text for the Azure Architecture Factory and surface "
    "any LLM-related capability signals the deterministic keyword scanner "
    "may have missed. Return a JSON object of the form "
    '{"additional_signals": ["<short label>", ...]}. '
    "Only include signals backed by explicit BRD wording. If nothing new is "
    "found, return {\"additional_signals\": []}. Do not restate the "
    "`already_detected` signals. Do not produce any user-visible text."
)


def build_classifier(settings: FactorySettings | None = None) -> ProjectClassifier:
    """Return the right classifier for the current environment.

    Tries the SDK runtime first when ``foundry_runtime_enabled`` is true
    and the SDK is importable. Falls back to the deterministic local
    classifier on any configuration or import failure so the factory is
    never taken offline by a missing preview dependency.
    """

    settings = settings or FactorySettings.from_env()
    local = LocalProjectClassifier()

    if not settings.foundry_runtime_enabled:
        return local

    try:  # Lazy import so missing SDK cannot crash the factory runner.
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import DefaultAzureCredential
    except ImportError:
        logger.info(
            "Agent Framework SDK not installed; factory classifier using local runtime."
        )
        return local

    try:
        credential = DefaultAzureCredential()
        client = FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model_deployment,
            credential=credential,
        )
        agent = Agent(
            client=client,
            name="FactoryProjectClassifier",
            instructions=_CLASSIFIER_INSTRUCTIONS,
        )
    except Exception as exc:  # pragma: no cover - credential / client failure
        logger.warning(
            "Foundry classifier construction failed, returning local runtime: %s",
            exc,
        )
        return local

    return FoundryProjectClassifier(agent=agent, local=local)


def classify_brd(brd_text: str, settings: FactorySettings | None = None) -> ClassificationResult:
    """Convenience entry point: build the classifier and run it once."""

    return build_classifier(settings).classify(brd_text)
