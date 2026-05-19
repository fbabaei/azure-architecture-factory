"""Integration smoke tests — FastAPI endpoints (using TestClient, no live Azure)."""
from __future__ import annotations

import sys
import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))


class TestOrchestratorAPI:
    def test_health_endpoint(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        from fastapi.testclient import TestClient
        from meta_orchestrator.main import create_app

        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_ready_endpoint(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        from fastapi.testclient import TestClient
        from meta_orchestrator.main import create_app

        client = TestClient(create_app())
        resp = client.get("/health/ready")
        assert resp.status_code == 200


class TestRegistryAPI:
    def test_health_endpoint(self, monkeypatch):
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        from fastapi.testclient import TestClient
        from agent_registry.main import create_app

        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_list_templates_returns_five_defaults(self, monkeypatch):
        monkeypatch.delenv("COSMOS_ENDPOINT", raising=False)
        from fastapi.testclient import TestClient
        from agent_registry.main import create_app

        client = TestClient(create_app())
        resp = client.get("/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5


class TestAgentFactoryAPI:
    def test_health_endpoint(self, monkeypatch):
        monkeypatch.setenv("AGENT_FRAMEWORK_ENABLED", "0")
        from fastapi.testclient import TestClient
        from agent_factory.main import create_app

        client = TestClient(create_app())
        resp = client.get("/health")
        assert resp.status_code == 200
