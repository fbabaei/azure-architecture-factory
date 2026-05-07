"""Smoke tests for the FastAPI wrapper.

These tests do NOT call Azure OpenAI; they patch `_init_team` so the
wrapper's HTTP contract can be validated in isolation. Per BRD FR-3 we
do not modify or directly test the upstream `build_team.py`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make `api` importable from src/.
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

# Set required env BEFORE importing the app so /health/ready can pass.
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-10-21")

from fastapi.testclient import TestClient  # noqa: E402

import api.main as main_module  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    # Stub the team so /ask doesn't hit AOAI.
    class FakeTeam:
        def ask(self, prompt: str):
            return ("fake answer", [{"agent": "security_sentinel", "request": prompt, "answer": "ok"}])

    monkeypatch.setattr(main_module, "_team", FakeTeam())
    monkeypatch.setattr(main_module, "_team_init_error", None)
    return TestClient(main_module.app)


def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready_returns_200_when_team_initialized(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"


def test_ask_validates_empty_prompt(client):
    r = client.post("/ask", json={"prompt": ""})
    assert r.status_code == 422


def test_ask_returns_answer_and_trace(client):
    r = client.post("/ask", json={"prompt": "Customer wants a Foundry POC milestone next week"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "fake answer"
    assert isinstance(body["trace"], list)
    assert any(hop["agent"] == "security_sentinel" for hop in body["trace"])


def test_health_ready_503_when_team_init_fails(monkeypatch):
    monkeypatch.setattr(main_module, "_team", None)
    monkeypatch.setattr(main_module, "_team_init_error", RuntimeError("boom"))
    c = TestClient(main_module.app)
    r = c.get("/health/ready")
    assert r.status_code == 503
    assert "team_init" in r.json()["detail"]
