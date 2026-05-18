import importlib
import os

from fastapi.testclient import TestClient


def _load_app(require_api_key: bool = False, rate_limit: int = 3):
    os.environ["REQUIRE_API_KEY"] = "true" if require_api_key else "false"
    os.environ["RATE_LIMIT_PER_MINUTE"] = str(rate_limit)
    os.environ["CSA_API_KEYS"] = "test-key"

    module = importlib.import_module("src.copilot_api.main")
    module = importlib.reload(module)
    return module.app


def test_health_and_ready_success_when_api_key_not_required():
    app = _load_app(require_api_key=False)
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_ready_fails_when_api_key_required_but_missing_configuration():
    os.environ["REQUIRE_API_KEY"] = "true"
    os.environ["CSA_API_KEYS"] = ""
    module = importlib.import_module("src.copilot_api.main")
    module = importlib.reload(module)
    client = TestClient(module.app)

    ready = client.get("/ready")
    assert ready.status_code == 503


def test_authenticated_tool_catalog_and_ask():
    app = _load_app(require_api_key=True)
    client = TestClient(app)

    unauthorized = client.get("/api/copilot/tools")
    assert unauthorized.status_code == 401

    headers = {"x-api-key": "test-key", "x-request-id": "req-001"}
    tools = client.get("/api/copilot/tools", headers=headers)
    assert tools.status_code == 200
    assert len(tools.json()["tools"]) >= 1

    ask = client.post(
        "/api/copilot/ask",
        json={"question": "How to reset MFA?", "context": "Internal runbook", "user_id": "user-1"},
        headers=headers,
    )
    assert ask.status_code == 200
    body = ask.json()
    assert body["source"] == "csa-support-mcp-v1"
    assert body["request_id"] == "req-001"
    assert isinstance(body["tools_used"], list)


def test_rate_limit_enforced():
    app = _load_app(require_api_key=False, rate_limit=1)
    client = TestClient(app)

    payload = {"question": "Q11", "context": "c", "user_id": "rate-user"}
    first = client.post("/api/copilot/ask", json=payload)
    assert first.status_code == 200

    second = client.post("/api/copilot/ask", json=payload)
    assert second.status_code == 429