"""Deterministic BRD readiness scoring and clarification generation.

This module implements the BRD readiness gate and scorecard guidance from:
- docs/BRD_READINESS_GATE.md
- docs/BRD_READINESS_SCORECARD.md

The output is designed to be machine-readable for portal/manifests while still
providing concise human-readable guidance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .project_classifier import ClassificationResult, score_brd


@dataclass(frozen=True)
class ReadinessCheckResult:
    """Single weighted scorecard check result."""

    key: str
    area: str
    label: str
    weight: int
    score: int  # 0 fail, 1 partial, 2 pass
    weighted_score: int
    blocking: bool = False


@dataclass
class BRDReadinessResult:
    """Structured readiness output for BRD intake."""

    classification: str  # Auto-Ready | Auto-Ready With Guardrails | Architect Review Required
    actual_weighted_score: int
    max_weighted_score: int
    percentage_score: int
    total_fails: int
    total_partials: int
    blockers: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    checks: list[ReadinessCheckResult] = field(default_factory=list)
    suggested_runtime: ClassificationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(item) for item in self.checks]
        if self.suggested_runtime is not None:
            payload["suggested_runtime"] = self.suggested_runtime.to_dict()
        return payload


# Weight model aligned to docs/BRD_READINESS_SCORECARD.md (max = 102).
_CHECK_DEFS: tuple[dict[str, Any], ...] = (
    # Scope
    {"key": "scope_objective", "area": "Scope", "label": "Primary business outcome is explicit", "weight": 2},
    {"key": "scope_personas", "area": "Scope", "label": "Main users, systems, or personas are identified", "weight": 2},
    {"key": "scope_capabilities", "area": "Scope", "label": "Core capabilities are bounded and specific", "weight": 2},
    {"key": "scope_success", "area": "Scope", "label": "Success criteria are stated", "weight": 1},
    # Workload Shape
    {"key": "shape_type", "area": "Workload Shape", "label": "Target workload type is recognizable", "weight": 2},
    {"key": "shape_interaction", "area": "Workload Shape", "label": "Interaction model is clear", "weight": 2},
    {"key": "shape_boundaries", "area": "Workload Shape", "label": "Service boundaries or domains can be inferred", "weight": 2},
    {"key": "shape_not_vague_combo", "area": "Workload Shape", "label": "Request is not a vague combination of unrelated systems", "weight": 1},
    # Azure Fit (all blocking)
    {"key": "azure_required", "area": "Azure Fit", "label": "Azure is explicitly required or clearly acceptable", "weight": 3, "blocking": True},
    {"key": "azure_hosting_map", "area": "Azure Fit", "label": "Hosting model maps to Azure services", "weight": 3, "blocking": True},
    {"key": "azure_integrations", "area": "Azure Fit", "label": "Required integrations are Azure-compatible", "weight": 3, "blocking": True},
    {"key": "azure_no_conflict", "area": "Azure Fit", "label": "No hard dependency contradicts Azure-first delivery", "weight": 3, "blocking": True},
    # Data
    {"key": "data_entities", "area": "Data", "label": "Main data entities or documents are named", "weight": 2},
    {"key": "data_io", "area": "Data", "label": "Inputs and outputs are identified", "weight": 2},
    {"key": "data_integrations", "area": "Data", "label": "External integrations are described", "weight": 2},
    {"key": "data_sensitivity", "area": "Data", "label": "Data sensitivity or classification is mentioned", "weight": 2},
    # NFRs
    {"key": "nfr_security", "area": "NFRs", "label": "Security expectations are stated", "weight": 3},
    {"key": "nfr_availability", "area": "NFRs", "label": "Availability or resiliency expectations are stated", "weight": 2},
    {"key": "nfr_observability", "area": "NFRs", "label": "Monitoring or operational visibility is expected", "weight": 2},
    {"key": "nfr_environment", "area": "NFRs", "label": "Environment expectations are stated", "weight": 2},
    # Delivery Readiness
    {"key": "delivery_diagram", "area": "Delivery Readiness", "label": "Enough detail exists to create a diagram", "weight": 2},
    {"key": "delivery_source", "area": "Delivery Readiness", "label": "Enough detail exists to scaffold source structure", "weight": 2},
    {"key": "delivery_infra", "area": "Delivery Readiness", "label": "Enough detail exists to generate infra assumptions", "weight": 2},
    {"key": "delivery_tests", "area": "Delivery Readiness", "label": "Enough detail exists to derive testable paths", "weight": 2},
)

_MAX_WEIGHTED_SCORE = 102


def assess_brd_readiness(brd_text: str) -> BRDReadinessResult:
    """Evaluate BRD readiness and generate clarification prompts.

    Scoring scale:
    - 2 = pass
    - 1 = partial
    - 0 = fail
    """

    text = brd_text or ""
    lowered = text.lower()

    feature = {
        # scope
        "scope_objective": _has_any(lowered, "objective", "goal", "outcome", "problem statement", "business value"),
        "scope_personas": _has_any(lowered, "user", "persona", "actor", "stakeholder", "customer", "internal staff"),
        "scope_capabilities": _has_any(lowered, "functional requirement", "capabil", "feature", "must", "should"),
        "scope_success": _has_any(lowered, "success criteria", "kpi", "sla", "target", "acceptance criteria"),
        # shape
        "shape_type": _has_any(lowered, "api", "web app", "portal", "microservice", "event", "batch", "workflow", "aks"),
        "shape_interaction": _has_any(lowered, "synchronous", "asynchronous", "event-driven", "batch", "queue", "request/response"),
        "shape_boundaries": _has_any(lowered, "service", "domain", "bounded context", "module", "component"),
        "shape_not_vague_combo": not _has_any(lowered, "everything platform", "all-in-one", "do it all") and _has_any(lowered, "scope", "module", "service", "domain", "workflow"),
        # azure fit
        "azure_required": _has_any(lowered, "azure", "entra", "bicep", "azure ai", "container app", "app service"),
        "azure_hosting_map": _has_any(lowered, "container apps", "app service", "aks", "function app", "static web app", "api management"),
        "azure_integrations": _has_any(lowered, "event hub", "service bus", "storage", "cosmos", "sql", "postgres", "openai", "foundry"),
        "azure_no_conflict": not _has_any(lowered, "aws-only", "gcp-only", "must remain on aws", "must remain on gcp", "not azure"),
        # data
        "data_entities": _has_any(lowered, "entity", "document", "record", "ticket", "order", "customer", "schema"),
        "data_io": _has_any(lowered, "input", "output", "ingest", "export", "source", "sink"),
        "data_integrations": _has_any(lowered, "integrat", "api", "connector", "upstream", "downstream", "external system"),
        "data_sensitivity": _has_any(lowered, "pii", "phi", "confidential", "sensitive", "classification", "gdpr", "hipaa"),
        # nfr
        "nfr_security": _has_any(lowered, "security", "auth", "authorization", "rbac", "managed identity", "key vault"),
        "nfr_availability": _has_any(lowered, "availability", "resilien", "rto", "rpo", "uptime", "ha", "dr"),
        "nfr_observability": _has_any(lowered, "monitor", "logging", "telemetry", "alert", "application insights", "observability"),
        "nfr_environment": _has_any(lowered, "dev", "test", "prod", "staging", "environment"),
        # delivery
        "delivery_diagram": _has_any(lowered, "architecture", "diagram", "component", "flow"),
        "delivery_source": _has_any(lowered, "service", "api", "frontend", "backend", "microservice", "repo", "language"),
        "delivery_infra": _has_any(lowered, "bicep", "terraform", "infrastructure", "iac", "resource group"),
        "delivery_tests": _has_any(lowered, "acceptance", "test", "validation", "smoke", "integration test"),
    }

    checks: list[ReadinessCheckResult] = []
    blockers: list[str] = []
    for check_def in _CHECK_DEFS:
        key = check_def["key"]
        score = _score_feature(feature[key], lowered, key)
        weighted = score * int(check_def["weight"])
        is_blocking = bool(check_def.get("blocking", False) and score == 0)
        checks.append(
            ReadinessCheckResult(
                key=key,
                area=check_def["area"],
                label=check_def["label"],
                weight=int(check_def["weight"]),
                score=score,
                weighted_score=weighted,
                blocking=is_blocking,
            )
        )
        if is_blocking:
            blockers.append(check_def["label"])

    actual_weighted_score = sum(item.weighted_score for item in checks)
    total_fails = sum(1 for item in checks if item.score == 0)
    total_partials = sum(1 for item in checks if item.score == 1)
    percentage = int(round((actual_weighted_score / _MAX_WEIGHTED_SCORE) * 100))

    if _is_architect_review_required(blockers, total_fails, lowered, percentage):
        classification = "Architect Review Required"
    elif percentage >= 80:
        classification = "Auto-Ready"
    else:
        classification = "Auto-Ready With Guardrails"

    guardrails = _build_guardrails(checks, classification)
    clarification_questions = _build_clarification_questions(checks)

    return BRDReadinessResult(
        classification=classification,
        actual_weighted_score=actual_weighted_score,
        max_weighted_score=_MAX_WEIGHTED_SCORE,
        percentage_score=percentage,
        total_fails=total_fails,
        total_partials=total_partials,
        blockers=blockers,
        guardrails=guardrails,
        clarification_questions=clarification_questions,
        checks=checks,
        suggested_runtime=score_brd(brd_text),
    )


def _has_any(text: str, *needles: str) -> bool:
    return any(needle in text for needle in needles)


def _score_feature(flag: bool, lowered: str, key: str) -> int:
    """Return 0/1/2 with a conservative partial signal."""

    if flag:
        return 2

    # If BRD is long and contains related terms, count as partial for a few checks.
    if len(lowered) > 800 and key in {
        "scope_success",
        "shape_boundaries",
        "data_sensitivity",
        "nfr_availability",
        "nfr_observability",
        "delivery_tests",
    }:
        return 1

    return 0


def _is_architect_review_required(
    blockers: list[str], total_fails: int, lowered: str, percentage: int
) -> bool:
    if blockers:
        return True
    if total_fails > 2:
        return True
    if percentage < 60:
        return True

    identity_missing = not _has_any(
        lowered,
        "entra",
        "identity",
        "authentication",
        "auth",
        "managed identity",
        "service principal",
    )
    network_missing = not _has_any(
        lowered,
        "vnet",
        "private endpoint",
        "network",
        "subnet",
        "ingress",
        "egress",
    )
    compliance_missing = not _has_any(
        lowered, "compliance", "gdpr", "hipaa", "soc2", "iso 27001", "policy"
    )
    return identity_missing or network_missing or compliance_missing


def _build_guardrails(checks: list[ReadinessCheckResult], classification: str) -> list[str]:
    if classification == "Auto-Ready":
        return []

    guardrails: list[str] = []
    for item in checks:
        if item.score <= 1 and item.area in {"Azure Fit", "NFRs", "Data"}:
            guardrails.append(item.label)
    # keep concise and stable
    return guardrails[:8]


def _build_clarification_questions(checks: list[ReadinessCheckResult]) -> list[str]:
    question_map = {
        "scope_objective": "What is the primary measurable business outcome for this project?",
        "scope_personas": "Who are the primary users or system actors for this solution?",
        "scope_capabilities": "What are the top functional capabilities that must be delivered first?",
        "scope_success": "What acceptance criteria or KPIs determine success?",
        "shape_type": "What workload type should be built first: web app, API, workflow, or microservices?",
        "shape_interaction": "Is the primary interaction synchronous API, event-driven, batch, or mixed?",
        "shape_boundaries": "What are the intended service or domain boundaries?",
        "azure_required": "Should this solution be Azure-first, and are non-Azure dependencies allowed?",
        "azure_hosting_map": "Which Azure hosting targets are preferred: Container Apps, App Service, AKS, or Functions?",
        "azure_integrations": "Which required integrations must be supported at launch?",
        "azure_no_conflict": "Are there any hard platform constraints that conflict with Azure deployment?",
        "data_entities": "What are the main business entities or document types the system manages?",
        "data_io": "What are the authoritative input sources and required output sinks?",
        "data_integrations": "Which external systems must be integrated, and who owns each interface?",
        "data_sensitivity": "What data classification applies: public, internal, confidential, or regulated?",
        "nfr_security": "What are the required authentication, authorization, and secret-management expectations?",
        "nfr_availability": "What availability, resiliency, or recovery targets are required?",
        "nfr_observability": "What monitoring, logging, and alerting requirements are expected?",
        "nfr_environment": "Which environments are required (dev, test, prod), and what promotion flow is expected?",
        "delivery_diagram": "Do you want the generated output to include a formal architecture diagram?",
        "delivery_source": "Which implementation language/runtime should be used for generated services?",
        "delivery_infra": "Should infrastructure be generated using Bicep, Terraform, or both?",
        "delivery_tests": "What minimum automated tests are required before deployment approval?",
    }

    questions: list[str] = []
    for item in checks:
        if item.score == 0 and item.key in question_map:
            questions.append(question_map[item.key])
    return questions[:12]
