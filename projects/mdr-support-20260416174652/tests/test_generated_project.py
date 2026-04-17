"""Smoke tests for the regenerated MDR extraction agent."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mdr_agent.main import app  # noqa: E402
from mdr_agent.models import MANDATORY_FIELDS, MDRArrangement  # noqa: E402
from mdr_agent.services.clarification_service import find_missing_fields  # noqa: E402


SAMPLE_TEXT = b"""
Reference: EY-MDR-2026-0042

Arrangement summary: A cross-border financing arrangement between the Luxembourg
parent and the Irish subsidiary leveraging hallmark C1bi and hallmark E3.

Implementation date: 2026-01-15

Jurisdictions involved: LU, IE, DE
"""


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_generated_project_layout_exists() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "DEPLOY.md",
        ROOT / "requirements.txt",
        ROOT / "src" / "mdr_agent" / "main.py",
        ROOT / "src" / "mdr_agent" / "models.py",
        ROOT / "src" / "mdr_agent" / "services" / "extraction_agent.py",
        ROOT / "src" / "mdr_agent" / "services" / "clarification_service.py",
        ROOT / "src" / "mdr_agent" / "services" / "document_ingestion.py",
        ROOT / "src" / "mdr_agent" / "services" / "repository.py",
        ROOT / "src" / "mdr_agent" / "services" / "chat_session.py",
        ROOT / "src" / "mdr_agent" / "services" / "qa_service.py",
        ROOT / "docs" / "architecture-overview.md",
        ROOT / "docs" / "detailed-architecture.md",
        ROOT / "docs" / "governance-model.md",
        ROOT / "docs" / "delivery-milestones.md",
        ROOT / "docs" / "success-criteria.md",
        ROOT / "docs" / "traceability-matrix.md",
        ROOT / "diagrams" / "mdr-support-20260416174652.md",
        ROOT / "diagrams" / "mdr-support-20260416174652.drawio",
        ROOT / "diagrams" / "mdr-support-20260416174652-detailed-architecture.md",
        ROOT / "diagrams" / "mdr-support-20260416174652-detailed-architecture.drawio",
        ROOT / "project-manifest.json",
        ROOT / "infra" / "main.bicep",
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Missing generated files: {missing}"


def test_health_endpoint(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_clarification_detects_all_missing_fields_on_empty_draft() -> None:
    empty = MDRArrangement()
    missing = find_missing_fields(empty)
    assert set(missing) == set(MANDATORY_FIELDS)


def test_upload_returns_arrangement_id_and_clarifications(client: TestClient) -> None:
    files = {"file": ("arrangement.txt", io.BytesIO(SAMPLE_TEXT), "text/plain")}
    r = client.post("/arrangements/upload", files=files)
    assert r.status_code == 200, r.text
    arrangement_id = r.json()["arrangement_id"]

    bundle = client.get(f"/arrangements/{arrangement_id}/clarifications").json()
    assert bundle["arrangement_id"] == arrangement_id
    # Heuristic extractor can't resolve parties from freeform text.
    assert "parties" in bundle["missing_fields"]


def test_chat_loop_drives_arrangement_to_complete(client: TestClient) -> None:
    files = {"file": ("blank.txt", io.BytesIO(b"placeholder text"), "text/plain")}
    arrangement_id = client.post("/arrangements/upload", files=files).json()[
        "arrangement_id"
    ]
    answers = {
        "reference": "EY-MDR-2026-0099",
        "summary": "Cross-border financing arrangement.",
        "implementation_date": "2026-02-01",
        "hallmarks": "C1bi, E3",
        "parties": "Acme LuxCo (intermediary, LU); Acme IE (relevant_taxpayer, IE)",
        "jurisdictions": "LU, IE, DE",
    }
    for _ in range(len(MANDATORY_FIELDS) + 1):
        bundle = client.get(
            f"/arrangements/{arrangement_id}/clarifications"
        ).json()
        if bundle["is_complete"]:
            break
        field = bundle["missing_fields"][0]
        r = client.post(
            f"/arrangements/{arrangement_id}/chat",
            json={"arrangement_id": arrangement_id, "message": answers[field]},
        )
        assert r.status_code == 200, r.text

    draft = client.post(f"/arrangements/{arrangement_id}/draft")
    assert draft.status_code == 200, draft.text
    assert draft.json()["is_complete"] is True


def test_mdr_qa_endpoint_answers_hallmark_question(client: TestClient) -> None:
    r = client.post("/qa", json={"question": "What is a hallmark under DAC6?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["question"] == "What is a hallmark under DAC6?"
    assert "hallmark" in body["answer"].lower()
    assert body["model"]


def test_mdr_qa_endpoint_rejects_empty_question(client: TestClient) -> None:
    r = client.post("/qa", json={"question": ""})
    assert r.status_code == 422


def test_api_session_lifecycle(client: TestClient) -> None:
    created = client.post("/api/session")
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]

    fetched = client.get(f"/api/session/{session_id}")
    assert fetched.status_code == 404

    seed = client.put(
        f"/api/case/{session_id}",
        json={
            "arrangement_id": session_id,
            "reference": "EY-MDR-2026-0190",
            "summary": "Session snapshot should become retrievable once case state exists.",
        },
    )
    assert seed.status_code == 200, seed.text

    fetched_after_seed = client.get(f"/api/session/{session_id}")
    assert fetched_after_seed.status_code == 200, fetched_after_seed.text
    snapshot = fetched_after_seed.json()
    assert snapshot["session_id"] == session_id
    assert snapshot["arrangement"] is not None

    deleted = client.delete(f"/api/session/{session_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/api/session/{session_id}")
    assert missing.status_code == 404


def test_api_chat_routes_off_topic_messages(client: TestClient) -> None:
    r = client.post("/api/chat", json={"message": "What is the weather forecast?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "off_topic"
    assert body["arrangement"] is None
    assert body["clarifications"] is None
    assert "MDR/DAC6" in body["reply"]


def test_api_chat_routes_to_qa_when_no_session_case_exists(client: TestClient) -> None:
    r = client.post(
        "/api/chat",
        json={"message": "Explain DAC6 hallmark C1 and main benefit test."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "qa"
    assert body["arrangement"] is None
    assert body["clarifications"] is None
    assert body["reply"]


def test_api_chat_routes_to_clarification_when_case_exists(client: TestClient) -> None:
    session_id = client.post("/api/session").json()["session_id"]
    seed = client.put(
        f"/api/case/{session_id}",
        json={
            "arrangement_id": session_id,
            "reference": "EY-MDR-2026-0200",
            "summary": "Cross-border arrangement requiring follow-up details.",
            "implementation_date": "2026-03-01T00:00:00Z",
        },
    )
    assert seed.status_code == 200, seed.text

    r = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "C1bi, E3 and this should satisfy hallmark data",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "clarification"
    assert body["arrangement"] is not None
    assert body["clarifications"] is not None


def test_api_case_from_text_and_confirm_flow(client: TestClient) -> None:
    session_id = "session-from-text-001"
    created = client.post(
        "/api/case/from-text",
        json={
            "session_id": session_id,
            "reference": "EY-MDR-2026-0300",
            "text": (
                "MDR arrangement draft for DAC6 analysis involving hallmark C1bi "
                "and cross-border financing between LU and IE with known parties."
            ),
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["arrangement_id"] == session_id

    fetched = client.get(f"/api/case/{session_id}")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["arrangement_id"] == session_id

    complete_case_id = "session-complete-case-001"
    updated = client.put(
        f"/api/case/{complete_case_id}",
        json={
            "arrangement_id": complete_case_id,
            "reference": "EY-MDR-2026-0310",
            "summary": "Complete arrangement for confirm flow test.",
            "implementation_date": "2026-03-15T00:00:00Z",
            "hallmarks": [
                {"code": "C1bi", "category": "C", "description": "Cross-border deductible payments"}
            ],
            "parties": [
                {
                    "role": "intermediary",
                    "name": "Acme Advisory Lux",
                    "jurisdiction": "LU",
                },
                {
                    "role": "relevant_taxpayer",
                    "name": "Acme Ireland Ltd",
                    "jurisdiction": "IE",
                },
            ],
            "jurisdictions": ["LU", "IE", "DE"],
        },
    )
    assert updated.status_code == 200, updated.text

    confirmed = client.post(f"/api/case/{complete_case_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["is_complete"] is True
