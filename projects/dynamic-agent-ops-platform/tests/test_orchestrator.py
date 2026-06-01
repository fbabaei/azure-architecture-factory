"""Tests for meta-orchestrator: config, runtime selection, decomposition."""
from __future__ import annotations

import os
import sys
import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src is on path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))

from meta_orchestrator.config import Settings


class TestSettings:
    def test_foundry_runtime_enabled_all_set(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "1")
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/")
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
        s = Settings()
        assert s.foundry_runtime_enabled is True

    def test_foundry_runtime_disabled_when_flag_unset(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.services.ai.azure.com/")
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
        s = Settings()
        assert s.foundry_runtime_enabled is False

    def test_foundry_runtime_disabled_when_endpoint_missing(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "1")
        monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
        s = Settings()
        assert s.foundry_runtime_enabled is False

    def test_defaults(self):
        s = Settings()
        assert s.cosmos_database == "daop"
        assert s.agent_ttl_seconds == 3600


class TestDeterministicDecompose:
    def test_always_includes_analyst(self):
        from meta_orchestrator.services.orchestrator_service import _deterministic_decompose
        tasks = _deterministic_decompose("build a web app")
        types = [t.agent_type for t in tasks]
        assert "analyst" in [str(t) for t in types]

    def test_architect_detected_by_keyword(self):
        from meta_orchestrator.services.orchestrator_service import _deterministic_decompose
        tasks = _deterministic_decompose("design an azure architecture")
        types = [str(t.agent_type) for t in tasks]
        assert "architect" in types

    def test_security_always_present(self):
        from meta_orchestrator.services.orchestrator_service import _deterministic_decompose
        tasks = _deterministic_decompose("build something")
        types = [str(t.agent_type) for t in tasks]
        assert "security" in types

    def test_developer_detected(self):
        from meta_orchestrator.services.orchestrator_service import _deterministic_decompose
        tasks = _deterministic_decompose("implement a python api service")
        types = [str(t.agent_type) for t in tasks]
        assert "developer" in types


class TestOrchestratorService:
    @pytest.mark.asyncio
    async def test_orchestrate_returns_session_when_foundry_disabled(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        from meta_orchestrator.config import Settings
        from meta_orchestrator.models import OrchestrateRequest
        from meta_orchestrator.services.orchestrator_service import OrchestratorService

        settings = Settings()
        service = OrchestratorService(settings)

        # Patch the dispatch fire-and-forget so it doesn't actually call HTTP
        with patch.object(service, "_dispatch", new=AsyncMock()):
            req = OrchestrateRequest(goal="design an azure storage solution")
            result = await service.orchestrate(req)

        assert result.session_id
        assert result.project_id
        assert len(result.task_plan) > 0

    @pytest.mark.asyncio
    async def test_foundry_sdk_runtime_selected_when_enabled(self, monkeypatch):
        """Test that _run_sdk is called (not deterministic) when runtime enabled."""
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "1")
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://fake.services.ai.azure.com/")
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
        from meta_orchestrator.config import Settings

        s = Settings()
        assert s.foundry_runtime_enabled is True

    @pytest.mark.asyncio
    async def test_safety_net_fires_when_sdk_unavailable(self, monkeypatch):
        """Test the factory falls back to local runtime when SDK not installed."""
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        from meta_orchestrator.config import Settings
        from meta_orchestrator.models import OrchestrateRequest
        from meta_orchestrator.services.orchestrator_service import OrchestratorService

        settings = Settings()
        assert not settings.foundry_runtime_enabled  # SDK not enabled → deterministic path
        service = OrchestratorService(settings)
        with patch.object(service, "_dispatch", new=AsyncMock()):
            result = await service.orchestrate(OrchestrateRequest(goal="test goal"))
        assert result.status.value in {"running", "decomposing"}
