"""End-to-end API flow tests with all Azure-backed collaborators faked.

These exercise the full FastAPI request/response path (routing, validation,
serialization) while monkeypatching the lazy router accessors so no real Azure
connectivity is required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from casewright.api.main import app
from casewright.api.routers import chat, pipeline, sharepoint
from casewright.core.models import ChatResponse, ChatTurn, Citation, IndexerStatus

client = TestClient(app)


def test_chat_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    history = AsyncMock()
    history.get_turns.return_value = []
    history.append_turns.return_value = None

    agent = AsyncMock()
    agent.answer.return_value = ChatResponse(
        conversation_id="c1",
        answer="Grounded answer.",
        citations=[Citation(document_title="Doc A", source_path="sites/a/doc.pdf", score=3.1)],
        runtime="local",
    )

    monkeypatch.setattr(chat, "_get_history", lambda: history)
    monkeypatch.setattr(chat, "_get_agent", lambda: agent)

    resp = client.post("/api/chat", json={"message": "hello", "conversation_id": "c1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Grounded answer."
    assert body["runtime"] == "local"
    assert body["citations"][0]["document_title"] == "Doc A"
    history.append_turns.assert_awaited_once()


def test_chat_rejects_empty_message() -> None:
    resp = client.post("/api/chat", json={"message": "   ", "conversation_id": "c1"})
    assert resp.status_code == 400


def test_get_history_returns_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    history = AsyncMock()
    history.get_turns.return_value = [
        ChatTurn(role="user", content="hi"),
        ChatTurn(role="assistant", content="hello"),
    ]
    monkeypatch.setattr(chat, "_get_history", lambda: history)

    resp = client.get("/api/chat/conv-1")

    assert resp.status_code == 200
    turns = resp.json()
    assert [t["role"] for t in turns] == ["user", "assistant"]


def test_pipeline_setup_run_and_status(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = AsyncMock()
    fake.setup.return_value = None
    fake.run_indexer.return_value = None
    fake.get_indexer_status.return_value = IndexerStatus(
        indexer_name="casewright-multimodal-indexer",
        status="success",
        items_processed=42,
    )
    monkeypatch.setattr(pipeline, "_get_pipeline", lambda: fake)

    assert client.post("/api/pipeline/setup-pipeline").json() == {"status": "configured"}

    run = client.post("/api/pipeline/run-indexer")
    assert run.status_code == 200
    assert run.json()["status"] == "started"

    status = client.get("/api/pipeline/indexer-status")
    assert status.status_code == 200
    assert status.json()["items_processed"] == 42


def test_pipeline_status_404_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = AsyncMock()
    fake.get_indexer_status.return_value = None
    monkeypatch.setattr(pipeline, "_get_pipeline", lambda: fake)

    resp = client.get("/api/pipeline/indexer-status")
    assert resp.status_code == 404


def test_sharepoint_sync_site_enqueues(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatcher = AsyncMock()
    monkeypatch.setattr(sharepoint, "_get_dispatcher", lambda: dispatcher)

    resp = client.post("/api/sharepoint/sites/sync-site", params={"site_id": "site-123"})

    assert resp.status_code == 200
    assert resp.json() == {"status": "queued", "site_id": "site-123"}
    dispatcher.enqueue.assert_awaited_once()


def test_sharepoint_sync_all_counts_sites(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = AsyncMock()
    graph.list_sites.return_value = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    dispatcher = AsyncMock()
    monkeypatch.setattr(sharepoint, "_get_graph", lambda: graph)
    monkeypatch.setattr(sharepoint, "_get_dispatcher", lambda: dispatcher)

    resp = client.post("/api/sharepoint/sites/sync")

    assert resp.status_code == 200
    assert resp.json() == {"queued": 3}
    assert dispatcher.enqueue.await_count == 3
