"""API smoke tests that require no Azure connectivity."""
from __future__ import annotations

from fastapi.testclient import TestClient

from casewright.api.main import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "casewright-api"
