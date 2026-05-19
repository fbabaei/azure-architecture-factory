"""Tests for agent registry service."""
from __future__ import annotations

import sys
import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))


class TestRegistryService:
    @pytest.mark.asyncio
    async def test_list_templates_returns_defaults(self, monkeypatch):
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        from agent_registry.config import Settings
        from agent_registry.services.registry_service import RegistryService

        service = RegistryService(Settings())
        templates = await service.list_templates()
        assert len(templates) == 5
        types = {t.agent_type for t in templates}
        assert types == {"architect", "developer", "ops", "analyst", "security"}

    @pytest.mark.asyncio
    async def test_filter_by_agent_type(self, monkeypatch):
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        from agent_registry.config import Settings
        from agent_registry.services.registry_service import RegistryService

        service = RegistryService(Settings())
        templates = await service.list_templates(agent_type="architect")
        assert all(t.agent_type == "architect" for t in templates)
        assert len(templates) >= 1

    @pytest.mark.asyncio
    async def test_save_and_retrieve_template(self, monkeypatch):
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        from agent_registry.config import Settings
        from agent_registry.models import AgentTemplate
        from agent_registry.services.registry_service import RegistryService

        service = RegistryService(Settings())
        t = AgentTemplate(
            name="Test Agent",
            agent_type="developer",
            description="A test template",
            capabilities=["code_gen"],
        )
        await service.save_template(t)
        retrieved = await service.get_template(t.template_id)
        assert retrieved is not None
        assert retrieved.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_unknown_template_returns_none(self, monkeypatch):
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        from agent_registry.config import Settings
        from agent_registry.services.registry_service import RegistryService

        service = RegistryService(Settings())
        result = await service.get_template("non-existent-id-xyz")
        assert result is None
