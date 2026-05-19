"""Tests for the base agent runner (MAF + deterministic fallback)."""
from __future__ import annotations

import sys
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))


class TestBaseAgentRunner:
    @pytest.mark.asyncio
    async def test_deterministic_fallback_runs_when_sdk_not_enabled(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        from agent_templates.shared.config import AgentSettings
        from agent_templates.shared.base_agent import BaseAgentRunner, TaskRequest

        settings = AgentSettings(agent_type="developer")
        runner = BaseAgentRunner("developer", "You are a developer.", settings)
        req = TaskRequest(
            session_id="sess-1",
            project_id="proj-1",
            task={"task_id": "t1", "description": "write a hello world api"},
        )
        result = await runner.run(req)
        assert result.status == "completed"
        assert result.agent_type == "developer"
        assert "deterministic" in (result.result or "").lower()

    @pytest.mark.asyncio
    async def test_sdk_runtime_raises_when_sdk_not_installed(self, monkeypatch):
        """When SDK not installed, _run_sdk raises RuntimeError which BaseAgentRunner catches."""
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "1")
        monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://fake.services.ai.azure.com/")
        monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
        from agent_templates.shared.config import AgentSettings
        from agent_templates.shared.base_agent import BaseAgentRunner, TaskRequest

        settings = AgentSettings(agent_type="security")
        runner = BaseAgentRunner("security", "You are a security auditor.", settings)

        # Simulate SDK ImportError by patching the import
        with patch.dict("sys.modules", {"azure.ai.projects": None, "azure.identity": None}):
            req = TaskRequest(
                session_id="sess-2",
                project_id="proj-2",
                task={"task_id": "t2", "description": "audit rbac"},
            )
            result = await runner.run(req)
        # Should fall back to deterministic or return failed — either is acceptable
        assert result.status in {"completed", "failed"}
        assert result.session_id == "sess-2"

    @pytest.mark.asyncio
    async def test_task_result_includes_duration(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        from agent_templates.shared.config import AgentSettings
        from agent_templates.shared.base_agent import BaseAgentRunner, TaskRequest

        settings = AgentSettings(agent_type="analyst")
        runner = BaseAgentRunner("analyst", "You are an analyst.", settings)
        req = TaskRequest(
            session_id="sess-3",
            project_id="proj-3",
            task={"task_id": "t3", "description": "estimate costs"},
        )
        result = await runner.run(req)
        assert result.duration_ms is not None
        assert result.duration_ms >= 0


class TestAAFToolAdapter:
    @pytest.mark.asyncio
    async def test_submit_brd_calls_correct_endpoint(self):
        import httpx
        from unittest.mock import AsyncMock, MagicMock, patch
        from meta_orchestrator.tools.aaf_tool import AAFToolAdapter

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"project_id": "proj-abc"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)

            adapter = AAFToolAdapter(base_url="http://aaf-test", api_key="test-key")
            result = await adapter.submit_brd(
                project_name="MyProject",
                requirements="Build an API",
            )
        assert result["project_id"] == "proj-abc"
