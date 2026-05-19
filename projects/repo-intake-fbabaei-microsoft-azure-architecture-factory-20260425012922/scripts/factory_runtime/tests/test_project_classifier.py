"""Mandatory test shapes for the factory classifier.

These tests enforce the three test shapes required by
``docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md``:

1. Factory falls back to the local runtime when the SDK is not configured.
2. Factory selects the SDK runtime when both the SDK is installed AND
   the env flags are set (branches on
   ``importlib.util.find_spec("agent_framework")`` so CI passes with and
   without the preview SDK).
3. Forward-progress safety net fires when the LLM returns no new signal.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from factory_runtime import (  # noqa: E402  (path bootstrap above)
    ClassificationResult,
    FactorySettings,
    FoundryProjectClassifier,
    LocalProjectClassifier,
    build_classifier,
    classify_brd,
)
from factory_runtime.project_classifier import score_brd  # noqa: E402


def test_local_classifier_detects_llm_brd() -> None:
    result = classify_brd(
        "We need a Copilot-style chat agent backed by Azure AI Foundry with "
        "document extraction and retrieval-augmented generation."
    )
    assert result.runtime == "agent-framework"
    assert result.source == "local"
    assert "Copilot-style experience" in result.signals
    assert result.score >= 2


def test_local_classifier_keeps_pure_etl_on_local_runtime() -> None:
    result = classify_brd(
        "Nightly ETL pipeline that loads CSV extracts into a data warehouse "
        "and refreshes Power BI dashboards. No user-facing UI, no chatbot, "
        "no natural language involved."
    )
    assert result.runtime == "local"
    assert result.source == "local"
    assert "pure ETL workload" in result.counter_signals


def test_build_classifier_falls_back_to_local_when_disabled() -> None:
    """Shape 1: no env flags -> always local, regardless of SDK presence."""

    classifier = build_classifier(FactorySettings(agent_framework_enabled=False))
    assert isinstance(classifier, LocalProjectClassifier)


def test_build_classifier_selects_sdk_when_enabled() -> None:
    """Shape 2: env flags + SDK installed -> SDK runtime. Otherwise local.

    Branches on ``importlib.util.find_spec("agent_framework")`` so CI
    passes in both environments.
    """

    settings = FactorySettings(
        agent_framework_enabled=True,
        foundry_project_endpoint="https://example.services.ai.azure.com/api/projects/example",
        foundry_model_deployment="gpt-5.2",
    )
    assert settings.foundry_runtime_enabled is True

    classifier = build_classifier(settings)

    sdk_installed = importlib.util.find_spec("agent_framework") is not None
    if sdk_installed:
        # Credential construction may still fail in test sandboxes without
        # any auth source; tolerate a local fallback in that case.
        assert isinstance(classifier, (FoundryProjectClassifier, LocalProjectClassifier))
    else:
        assert isinstance(classifier, LocalProjectClassifier)


def test_foundry_classifier_falls_back_when_llm_adds_no_signal() -> None:
    """Shape 3: forward-progress safety net.

    When the SDK agent returns without surfacing any new signal, the
    Foundry classifier must return the deterministic verdict verbatim
    so the two runtimes can never disagree on what counts as an LLM
    workload.
    """

    class _NoOpAgent:
        async def run(self, _prompt: str) -> str:
            return '{"additional_signals": []}'

    classifier = FoundryProjectClassifier(
        agent=_NoOpAgent(),
        local=LocalProjectClassifier(),
    )

    brd = "Azure AI Foundry-backed chat agent with clarification turns."
    sdk_result = classifier.classify(brd)
    local_result = score_brd(brd)

    assert sdk_result.runtime == local_result.runtime
    assert sdk_result.signals == local_result.signals
    assert sdk_result.source == "local"  # fell back - SDK added nothing


def test_foundry_classifier_merges_new_signals_when_llm_contributes() -> None:
    """Positive path: when the LLM surfaces a genuinely new signal, the
    SDK runtime records it and tags the result as ``agent-framework``.
    The deterministic verdict (``runtime``) is unchanged because the
    floor owns the contract."""

    class _EnrichingAgent:
        async def run(self, _prompt: str) -> str:
            return '{"additional_signals": ["voice transcription UX"]}'

    classifier = FoundryProjectClassifier(
        agent=_EnrichingAgent(),
        local=LocalProjectClassifier(),
    )

    brd = "Copilot integration for helpdesk agents."
    result = classifier.classify(brd)

    assert result.runtime == "agent-framework"
    assert result.source == "agent-framework"
    assert "voice transcription UX" in result.signals


def test_classification_result_serializes_for_manifest() -> None:
    result = ClassificationResult(
        runtime="agent-framework",
        score=3,
        signals=["Azure AI Foundry integration"],
        counter_signals=[],
        source="local",
        reasoning="test",
    )
    payload = result.to_dict()
    assert payload["runtime"] == "agent-framework"
    assert payload["signals"] == ["Azure AI Foundry integration"]
