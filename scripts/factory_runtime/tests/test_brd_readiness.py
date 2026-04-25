from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from factory_runtime import assess_brd_readiness  # noqa: E402


def test_readiness_architect_review_when_azure_fit_fails() -> None:
    brd = (
        "Build an AWS-only data processing platform. "
        "Must remain on AWS and not Azure. "
        "Nightly ETL and dashboards."
    )

    result = assess_brd_readiness(brd)

    assert result.classification == "Architect Review Required"
    assert any("Azure" in blocker for blocker in result.blockers)
    assert result.total_fails >= 1


def test_readiness_auto_ready_for_strong_brd() -> None:
    brd = (
        "Objective: build an Azure customer support copilot for internal staff. "
        "Users: support agents and team leads. "
        "Functional requirements: chat interface, ticket lookup API, document extraction, and summarization. "
        "Interaction model: synchronous API plus event-driven queue processing for updates. "
        "Architecture: microservices with clear service boundaries. "
        "Hosting on Azure Container Apps with API Management and Azure AI Foundry. "
        "Integrations: Service Bus, Azure AI Search, Cosmos DB, and existing CRM API. "
        "Data entities: tickets, customers, and knowledge documents. "
        "Inputs from CRM and document repository, outputs to support dashboard and CRM updates. "
        "Data is confidential and includes PII. "
        "Security: Entra ID auth, RBAC, managed identity, and Key Vault. "
        "Network: private endpoints with VNet integration and controlled ingress/egress. "
        "Compliance: GDPR policy controls are required. "
        "Availability target 99.9 with resiliency and disaster recovery guidance. "
        "Observability with Application Insights, logs, and alerts. "
        "Environments: dev, test, prod. "
        "IaC with Bicep. "
        "Acceptance criteria include smoke, integration, and validation tests."
    )

    result = assess_brd_readiness(brd)

    assert result.classification == "Auto-Ready"
    assert result.percentage_score >= 80
    assert result.blockers == []
    assert result.suggested_runtime is not None
    assert result.suggested_runtime.runtime == "agent-framework"


def test_readiness_generates_clarification_questions_for_gaps() -> None:
    brd = (
        "Create an Azure web app for operations. "
        "Use Container Apps and a backend API."
    )

    result = assess_brd_readiness(brd)

    assert result.classification in {
        "Auto-Ready With Guardrails",
        "Architect Review Required",
    }
    assert len(result.clarification_questions) > 0
    assert any("users" in q.lower() or "actor" in q.lower() for q in result.clarification_questions)


def test_readiness_result_serialization() -> None:
    result = assess_brd_readiness("Azure API with dev/test/prod and security requirements")
    payload = result.to_dict()

    assert "classification" in payload
    assert "checks" in payload
    assert isinstance(payload["checks"], list)
    assert "suggested_runtime" in payload
