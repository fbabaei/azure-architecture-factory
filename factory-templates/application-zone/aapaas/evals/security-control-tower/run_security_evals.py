#!/usr/bin/env python3
"""Offline eval gate for AI Security Control Tower candidate offerings.

The evals validate the governance contract, not a live security backend:
- every case has complete evidence envelope fields;
- high-risk actions are recommend/draft/approval-gated only;
- destructive or externally visible actions are never autonomous;
- approval requirements are explicit and attributable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "evidence-schema.json"
CASES_PATH = ROOT / "cases.json"
TOOL_INTEGRATIONS_PATH = ROOT / "tool-integrations.json"
APPROVAL_WORKFLOWS_PATH = ROOT / "approval-workflows.json"
PILOT_READINESS_PATH = ROOT / "pilot-readiness.json"
CONNECTOR_PILOT_PATH = ROOT / "connector-pilot.json"
PILOT_EVIDENCE_PATH = ROOT / "pilot-evidence.json"
PRODUCTION_PILOT_PATH = ROOT / "production-pilot.json"
AAPAAS_ROOT = ROOT.parents[1]
CERTIFICATION_EVIDENCE_PATH = AAPAAS_ROOT / "operations" / "health" / "ai-security-control-tower-certification.generated.json"
EVIDENCE_DIR = ROOT / "evidence"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, name: str, detail: str, failures: list[dict]) -> None:
    if not condition:
        failures.append({"name": name, "detail": detail})


def evaluate_case(case: dict, schema: dict) -> list[dict]:
    failures: list[dict] = []
    case_id = str(case.get("caseId", "<missing>"))

    for field in schema["requiredTopLevelFields"]:
        check(field in case, "required_field", f"{case_id}: missing {field}", failures)

    check(case.get("lane") in schema["lanes"], "lane_allowed", f"{case_id}: invalid lane", failures)

    approval = case.get("approval") or {}
    approval_state = approval.get("state")
    check(
        approval_state in schema["approvalStates"],
        "approval_state_allowed",
        f"{case_id}: invalid approval state",
        failures,
    )

    evidence = case.get("evidence") or []
    check(bool(evidence), "evidence_present", f"{case_id}: evidence is empty", failures)
    allowed_evidence = set(schema["evidenceTypes"])
    for item in evidence:
        check(
            item.get("type") in allowed_evidence,
            "evidence_type_allowed",
            f"{case_id}: invalid evidence type {item.get('type')}",
            failures,
        )
        check(
            bool(item.get("source") or item.get("summary") or item.get("reference")),
            "evidence_has_content",
            f"{case_id}: evidence item lacks content",
            failures,
        )

    allowed_modes = set(schema["allowedActionModes"])
    forbidden = set(schema["forbiddenAutonomousActions"])
    actions = case.get("actions") or []
    check(bool(actions), "actions_present", f"{case_id}: actions are empty", failures)
    for action in actions:
        mode = action.get("mode")
        action_type = action.get("type")
        check(mode in allowed_modes, "action_mode_allowed", f"{case_id}: invalid mode {mode}", failures)
        check(action_type not in forbidden, "no_forbidden_action_type", f"{case_id}: forbidden action {action_type}", failures)
        if action_type in {"containment", "production_change", "pull_request_merge", "external_notification"}:
            check(
                mode == "approval_gated" and approval_state == "approved_by_human",
                "sensitive_action_requires_human_approval",
                f"{case_id}: sensitive action is not approved by a human",
                failures,
            )

    required_for = set(approval.get("requiredFor") or [])
    if required_for:
        check(
            approval_state in {"requires_human_approval", "approved_by_human"},
            "approval_required_when_sensitive",
            f"{case_id}: approval requirements need an approval state",
            failures,
        )
    if approval_state == "approved_by_human":
        check(bool(approval.get("approvedBy")), "approved_by_named_human", f"{case_id}: approvedBy missing", failures)

    return failures


def evaluate_tool_integrations(integrations: dict, schema: dict) -> list[dict]:
    failures: list[dict] = []
    allowed_lanes = set(schema["lanes"])
    allowed_evidence = set(schema["evidenceTypes"])

    read_only_sources = integrations.get("readOnlySources") or []
    draft_outputs = integrations.get("draftOnlyOutputs") or []
    check(bool(read_only_sources), "read_only_sources_present", "tool integrations: readOnlySources is empty", failures)
    check(bool(draft_outputs), "draft_only_outputs_present", "tool integrations: draftOnlyOutputs is empty", failures)

    for source in read_only_sources:
        integration_id = str(source.get("integrationId", "<missing>"))
        check(source.get("lane") in allowed_lanes, "integration_lane_allowed", f"{integration_id}: invalid lane", failures)
        check(source.get("accessMode") == "read_only", "source_access_read_only", f"{integration_id}: source is not read_only", failures)
        check(bool(source.get("dataBoundary")), "source_data_boundary_present", f"{integration_id}: missing data boundary", failures)
        for evidence_type in source.get("allowedEvidenceTypes") or []:
            check(evidence_type in allowed_evidence, "source_evidence_type_allowed", f"{integration_id}: invalid evidence type {evidence_type}", failures)
        forbidden_actions = set(source.get("forbiddenActions") or [])
        check(
            bool(forbidden_actions & {"exploit_execution", "repository_write", "production_change", "containment", "pull_request_merge", "external_notification"}),
            "source_forbidden_actions_explicit",
            f"{integration_id}: missing explicit forbidden sensitive actions",
            failures,
        )

    for output in draft_outputs:
        integration_id = str(output.get("integrationId", "<missing>"))
        check(output.get("lane") in allowed_lanes, "integration_lane_allowed", f"{integration_id}: invalid lane", failures)
        check(output.get("outputMode") == "draft_only", "output_mode_draft_only", f"{integration_id}: output is not draft_only", failures)
        check(
            output.get("promotionRequiresHumanApproval") is True,
            "output_promotion_requires_human_approval",
            f"{integration_id}: promotion does not require human approval",
            failures,
        )
        forbidden_actions = set(output.get("forbiddenActions") or [])
        check(
            bool(forbidden_actions & {"production_detection_enablement", "containment", "production_change", "pull_request_merge", "external_notification"}),
            "output_forbidden_actions_explicit",
            f"{integration_id}: missing explicit forbidden sensitive actions",
            failures,
        )

    return failures


def evaluate_approval_workflows(workflows_doc: dict, schema: dict) -> list[dict]:
    failures: list[dict] = []
    allowed_evidence = set(schema["evidenceTypes"])
    required_actions = set(workflows_doc.get("requiredSensitiveActions") or [])
    workflows = workflows_doc.get("approvalWorkflows") or []
    check(bool(workflows), "approval_workflows_present", "approval workflows: approvalWorkflows is empty", failures)

    workflow_actions = {
        str(workflow.get("sensitiveAction"))
        for workflow in workflows
        if isinstance(workflow, dict) and workflow.get("sensitiveAction")
    }
    check(
        required_actions.issubset(workflow_actions),
        "approval_workflows_cover_sensitive_actions",
        f"approval workflows: missing {sorted(required_actions - workflow_actions)}",
        failures,
    )

    for workflow in workflows:
        workflow_id = str(workflow.get("workflowId", "<missing>"))
        action = workflow.get("sensitiveAction")
        check(action in required_actions, "approval_action_required", f"{workflow_id}: unexpected sensitive action {action}", failures)
        check(workflow.get("executionMode") == "approval_gated", "approval_execution_mode_gated", f"{workflow_id}: not approval_gated", failures)
        check(
            workflow.get("requiresNamedHumanApproval") is True,
            "approval_requires_named_human",
            f"{workflow_id}: named human approval not required",
            failures,
        )
        check(bool(workflow.get("approverRole")), "approval_role_present", f"{workflow_id}: missing approverRole", failures)
        minimum_evidence = workflow.get("minimumEvidence") or []
        check(bool(minimum_evidence), "approval_minimum_evidence_present", f"{workflow_id}: missing minimumEvidence", failures)
        for evidence_type in minimum_evidence:
            check(evidence_type in allowed_evidence, "approval_evidence_type_allowed", f"{workflow_id}: invalid evidence type {evidence_type}", failures)
        audit_events = set(workflow.get("auditEvents") or [])
        for event_name in {"approval_requested", "approval_recorded", "action_executed_or_rejected"}:
            check(event_name in audit_events, "approval_audit_event_required", f"{workflow_id}: missing {event_name}", failures)
        check("audit_event" in minimum_evidence, "approval_audit_evidence_required", f"{workflow_id}: missing audit_event evidence", failures)
        check("rollbackRequired" in workflow, "approval_rollback_declared", f"{workflow_id}: rollbackRequired missing", failures)
        check(bool(workflow.get("rollbackPlan")), "approval_rollback_plan_present", f"{workflow_id}: rollbackPlan missing", failures)
        check(bool(workflow.get("notificationPolicy")), "approval_notification_policy_present", f"{workflow_id}: notificationPolicy missing", failures)

    return failures


def evaluate_certification_evidence(evidence: dict) -> list[dict]:
    failures: list[dict] = []
    check(evidence.get("evalGate") == "PASS", "certification_eval_gate_passed", "certification evidence: evalGate is not PASS", failures)
    check(int(evidence.get("caseCount", 0) or 0) >= 4, "certification_cases_present", "certification evidence: expected at least 4 cases", failures)
    check(int(evidence.get("toolIntegrationCount", 0) or 0) >= 8, "certification_tool_integrations_present", "certification evidence: expected at least 8 tool integrations", failures)
    check(int(evidence.get("approvalWorkflowCount", 0) or 0) >= 4, "certification_approval_workflows_present", "certification evidence: expected at least 4 approval workflows", failures)
    check(bool(evidence.get("certificationInterpretation")), "certification_interpretation_present", "certification evidence: interpretation missing", failures)
    return failures


def evaluate_pilot_readiness(readiness_doc: dict) -> list[dict]:
    failures: list[dict] = []
    pilot = readiness_doc.get("pilotReadiness") or {}
    checks = readiness_doc.get("readinessChecks") or []
    required_evidence = set(pilot.get("requiredEvidenceBeforePilot") or [])
    check(pilot.get("stage") == "controlled-preview", "pilot_stage_controlled_preview", "pilot readiness: stage must remain controlled-preview", failures)
    check(pilot.get("targetStage") == "production-pilot", "pilot_target_stage_declared", "pilot readiness: targetStage must be production-pilot", failures)
    check(
        pilot.get("overallStatus") == "blocked-until-tenant-prerequisites-complete",
        "pilot_blocked_until_prereqs",
        "pilot readiness: production pilot must remain blocked until prerequisites complete",
        failures,
    )
    check(bool(pilot.get("minimumApproverRole")), "pilot_minimum_approver_role_present", "pilot readiness: minimumApproverRole missing", failures)
    check(bool(checks), "pilot_readiness_checks_present", "pilot readiness: readinessChecks is empty", failures)

    check_evidence = {
        str(item.get("evidenceType"))
        for item in checks
        if isinstance(item, dict) and item.get("evidenceType")
    }
    check(
        required_evidence.issubset(check_evidence),
        "pilot_required_evidence_covered",
        f"pilot readiness: missing evidence {sorted(required_evidence - check_evidence)}",
        failures,
    )

    for item in checks:
        check_id = str(item.get("checkId", "<missing>"))
        check(item.get("status") == "required", "pilot_check_status_required", f"{check_id}: status must be required", failures)
        check(item.get("blocksProductionPilot") is True, "pilot_check_blocks_production", f"{check_id}: does not block production pilot", failures)
        check(bool(item.get("ownerRole")), "pilot_check_owner_present", f"{check_id}: ownerRole missing", failures)
        check(bool(item.get("description")), "pilot_check_description_present", f"{check_id}: description missing", failures)

    controls = readiness_doc.get("pilotControls") or []
    check(bool(controls), "pilot_controls_present", "pilot readiness: pilotControls is empty", failures)
    check(
        any("read-only" in str(control).lower() for control in controls),
        "pilot_controls_read_only_boundary",
        "pilot readiness: controls must mention read-only boundary",
        failures,
    )
    check(
        any("draft-only" in str(control).lower() for control in controls),
        "pilot_controls_draft_only_boundary",
        "pilot readiness: controls must mention draft-only boundary",
        failures,
    )
    return failures


def evaluate_connector_pilot(pilot_doc: dict) -> list[dict]:
    failures: list[dict] = []
    pilot = pilot_doc.get("connectorPilot") or {}
    connectors = pilot_doc.get("connectors") or []
    prerequisites = pilot_doc.get("pilotPrerequisites") or []
    controls = pilot_doc.get("rolloutControls") or []
    check(pilot.get("stage") == "connector-pilot-prep", "connector_pilot_stage_declared", "connector pilot: stage must be connector-pilot-prep", failures)
    check(pilot.get("activationMode") == "read_only_first", "connector_pilot_read_only_first", "connector pilot: activationMode must be read_only_first", failures)
    check(bool(pilot.get("minimumApproverRole")), "connector_pilot_approver_present", "connector pilot: minimumApproverRole missing", failures)
    check(bool(connectors), "connector_pilot_connectors_present", "connector pilot: connectors are empty", failures)
    for connector in connectors:
        connector_id = str(connector.get("connectorId", "<missing>"))
        check(connector.get("accessMode") == "read_only", "connector_access_read_only", f"{connector_id}: connector is not read_only", failures)
        check(connector.get("pilotStatus") in {"planned", "in-review", "ready"}, "connector_status_allowed", f"{connector_id}: invalid pilotStatus", failures)
        check(bool(connector.get("requiredOwnerRole")), "connector_owner_present", f"{connector_id}: requiredOwnerRole missing", failures)
        required_evidence = set(connector.get("requiredEvidence") or [])
        check({"tenant_connector_inventory", "rbac_review", "sample_read_only_query", "audit_log_mapping"}.issubset(required_evidence), "connector_required_evidence_complete", f"{connector_id}: missing required evidence", failures)
        forbidden = set(connector.get("forbiddenUntilApproved") or [])
        check(bool(forbidden), "connector_forbidden_actions_present", f"{connector_id}: forbiddenUntilApproved missing", failures)
    check(len(prerequisites) >= 3, "connector_prerequisites_present", "connector pilot: expected managed persistence, observability, and pilot scope prerequisites", failures)
    for prerequisite in prerequisites:
        prereq_id = str(prerequisite.get("prerequisiteId", "<missing>"))
        check(prerequisite.get("status") == "required", "connector_prerequisite_required", f"{prereq_id}: prerequisite status must be required", failures)
        check(bool(prerequisite.get("description")), "connector_prerequisite_description_present", f"{prereq_id}: description missing", failures)
    check(any("no connector writes" in str(control).lower() for control in controls), "connector_controls_no_writes", "connector pilot: controls must prohibit connector writes", failures)
    check(any("read-only" in str(control).lower() for control in controls), "connector_controls_read_only", "connector pilot: controls must mention read-only queries", failures)
    check(any("production pilot cannot start" in str(control).lower() for control in controls), "connector_controls_pilot_blocked", "connector pilot: controls must keep production pilot blocked", failures)
    return failures


def evaluate_pilot_evidence(evidence_doc: dict) -> list[dict]:
    failures: list[dict] = []
    capture = evidence_doc.get("evidenceCapture") or {}
    items = evidence_doc.get("captureItems") or []
    controls = evidence_doc.get("evidenceControls") or []
    check(capture.get("stage") == "pilot-evidence-capture", "evidence_capture_stage_declared", "pilot evidence: stage must be pilot-evidence-capture", failures)
    check(capture.get("overallStatus") == "ready-to-capture", "evidence_capture_ready", "pilot evidence: overallStatus must be ready-to-capture", failures)
    check(bool(capture.get("minimumApproverRole")), "evidence_capture_approver_present", "pilot evidence: minimumApproverRole missing", failures)
    check(bool(capture.get("evidenceStore")), "evidence_store_declared", "pilot evidence: evidenceStore missing", failures)
    check(bool(items), "evidence_capture_items_present", "pilot evidence: captureItems is empty", failures)
    categories = {
        str(item.get("category"))
        for item in items
        if isinstance(item, dict) and item.get("category")
    }
    check(
        {"connectors", "approvals", "rollback", "observability", "compliance"}.issubset(categories),
        "evidence_capture_categories_complete",
        f"pilot evidence: missing categories {sorted({'connectors', 'approvals', 'rollback', 'observability', 'compliance'} - categories)}",
        failures,
    )
    for item in items:
        capture_id = str(item.get("captureId", "<missing>"))
        check(item.get("status") == "required", "evidence_capture_status_required", f"{capture_id}: status must be required", failures)
        check(bool(item.get("ownerRole")), "evidence_capture_owner_present", f"{capture_id}: ownerRole missing", failures)
        check(len(item.get("requiredArtifacts") or []) >= 3, "evidence_capture_artifacts_present", f"{capture_id}: expected at least 3 required artifacts", failures)
        check(bool(item.get("description")), "evidence_capture_description_present", f"{capture_id}: description missing", failures)
    check(any("approved tenant storage" in str(control).lower() for control in controls), "evidence_controls_tenant_storage", "pilot evidence: controls must require approved tenant storage", failures)
    check(any("do not paste raw sensitive findings" in str(control).lower() for control in controls), "evidence_controls_no_raw_findings", "pilot evidence: controls must prohibit raw sensitive findings in portal cards", failures)
    check(any("production pilot remains blocked" in str(control).lower() for control in controls), "evidence_controls_pilot_blocked", "pilot evidence: controls must keep production pilot blocked", failures)
    return failures


def evaluate_production_pilot(pilot_doc: dict) -> list[dict]:
    failures: list[dict] = []
    pilot = pilot_doc.get("productionPilot") or {}
    scope = pilot_doc.get("pilotScope") or {}
    criteria = pilot_doc.get("goNoGoCriteria") or []
    controls = pilot_doc.get("enablementControls") or []
    check(pilot.get("stage") == "production-pilot-enablement", "production_pilot_stage_declared", "production pilot: stage must be production-pilot-enablement", failures)
    check(pilot.get("overallStatus") == "blocked-pending-go-no-go-approval", "production_pilot_go_no_go_blocked", "production pilot: must remain blocked pending go/no-go approval", failures)
    check(pilot.get("scopeMode") == "limited-scope-pilot", "production_pilot_limited_scope", "production pilot: scopeMode must be limited-scope-pilot", failures)
    check(pilot.get("requiresNamedGoNoGoDecision") is True, "production_pilot_named_decision", "production pilot: named go/no-go decision required", failures)
    check(bool(pilot.get("minimumApproverRole")), "production_pilot_approver_present", "production pilot: minimumApproverRole missing", failures)
    check(bool(scope.get("tenantScope")), "production_pilot_tenant_scope_present", "production pilot: tenantScope missing", failures)
    check(bool(scope.get("connectorScope")), "production_pilot_connector_scope_present", "production pilot: connectorScope missing", failures)
    check("approval-gated" in str(scope.get("actionScope", "")).lower(), "production_pilot_action_scope_gated", "production pilot: actionScope must mention approval-gated actions", failures)
    check(bool(criteria), "production_pilot_criteria_present", "production pilot: goNoGoCriteria is empty", failures)
    criterion_ids = {
        str(item.get("criterionId"))
        for item in criteria
        if isinstance(item, dict) and item.get("criterionId")
    }
    check(
        {"evidence-capture-complete", "owner-signoff", "rollback-ready", "communications-approved"}.issubset(criterion_ids),
        "production_pilot_required_criteria_present",
        "production pilot: missing required go/no-go criteria",
        failures,
    )
    for item in criteria:
        criterion_id = str(item.get("criterionId", "<missing>"))
        check(item.get("status") == "required", "production_pilot_criterion_required", f"{criterion_id}: status must be required", failures)
        check(item.get("blocksEnablement") is True, "production_pilot_criterion_blocks", f"{criterion_id}: criterion must block enablement", failures)
        check(bool(item.get("ownerRole")), "production_pilot_criterion_owner", f"{criterion_id}: ownerRole missing", failures)
        check(len(item.get("requiredEvidence") or []) >= 3, "production_pilot_criterion_evidence", f"{criterion_id}: expected at least 3 evidence items", failures)
    check(any("blocked until named go/no-go approval" in str(control).lower() for control in controls), "production_pilot_controls_blocked", "production pilot: controls must keep pilot blocked until named approval", failures)
    check(any("read-only connectors" in str(control).lower() for control in controls), "production_pilot_controls_read_only", "production pilot: controls must require read-only connectors", failures)
    check(any("draft-only outputs" in str(control).lower() for control in controls), "production_pilot_controls_draft_only", "production pilot: controls must require draft-only outputs", failures)
    return failures


def main() -> int:
    schema = load_json(SCHEMA_PATH)
    cases = load_json(CASES_PATH)
    tool_integrations = load_json(TOOL_INTEGRATIONS_PATH)
    approval_workflows = load_json(APPROVAL_WORKFLOWS_PATH)
    pilot_readiness = load_json(PILOT_READINESS_PATH)
    connector_pilot = load_json(CONNECTOR_PILOT_PATH)
    pilot_evidence = load_json(PILOT_EVIDENCE_PATH)
    production_pilot = load_json(PRODUCTION_PILOT_PATH)
    certification_evidence = load_json(CERTIFICATION_EVIDENCE_PATH)
    all_failures: list[dict] = []
    results = []

    for case in cases:
        failures = evaluate_case(case, schema)
        results.append({
            "caseId": case.get("caseId"),
            "lane": case.get("lane"),
            "passed": not failures,
            "failures": failures,
        })
        all_failures.extend(failures)

    integration_failures = evaluate_tool_integrations(tool_integrations, schema)
    all_failures.extend(integration_failures)
    approval_failures = evaluate_approval_workflows(approval_workflows, schema)
    all_failures.extend(approval_failures)
    certification_failures = evaluate_certification_evidence(certification_evidence)
    all_failures.extend(certification_failures)
    pilot_failures = evaluate_pilot_readiness(pilot_readiness)
    all_failures.extend(pilot_failures)
    connector_failures = evaluate_connector_pilot(connector_pilot)
    all_failures.extend(connector_failures)
    evidence_failures = evaluate_pilot_evidence(pilot_evidence)
    all_failures.extend(evidence_failures)
    production_pilot_failures = evaluate_production_pilot(production_pilot)
    all_failures.extend(production_pilot_failures)

    summary = {
        "gate": "PASS" if not all_failures else "FAIL",
        "caseCount": len(cases),
        "passedCount": len([item for item in results if item["passed"]]),
        "failedCount": len([item for item in results if not item["passed"]]),
        "toolIntegrationCount": len(tool_integrations.get("readOnlySources", [])) + len(tool_integrations.get("draftOnlyOutputs", [])),
        "toolIntegrationFailures": integration_failures,
        "approvalWorkflowCount": len(approval_workflows.get("approvalWorkflows", [])),
        "approvalWorkflowFailures": approval_failures,
        "certificationEvidenceFailures": certification_failures,
        "pilotReadinessCheckCount": len(pilot_readiness.get("readinessChecks", [])),
        "pilotReadinessFailures": pilot_failures,
        "connectorPilotCount": len(connector_pilot.get("connectors", [])),
        "connectorPilotFailures": connector_failures,
        "pilotEvidenceCaptureCount": len(pilot_evidence.get("captureItems", [])),
        "pilotEvidenceFailures": evidence_failures,
        "productionPilotCriteriaCount": len(production_pilot.get("goNoGoCriteria", [])),
        "productionPilotFailures": production_pilot_failures,
        "results": results,
        "blockingChecks": [
            "required_field",
            "lane_allowed",
            "approval_state_allowed",
            "evidence_present",
            "evidence_type_allowed",
            "evidence_has_content",
            "actions_present",
            "action_mode_allowed",
            "no_forbidden_action_type",
            "sensitive_action_requires_human_approval",
            "approval_required_when_sensitive",
            "approved_by_named_human",
            "read_only_sources_present",
            "draft_only_outputs_present",
            "source_access_read_only",
            "source_data_boundary_present",
            "source_forbidden_actions_explicit",
            "output_mode_draft_only",
            "output_promotion_requires_human_approval",
            "output_forbidden_actions_explicit",
            "approval_workflows_present",
            "approval_workflows_cover_sensitive_actions",
            "approval_execution_mode_gated",
            "approval_requires_named_human",
            "approval_role_present",
            "approval_minimum_evidence_present",
            "approval_audit_event_required",
            "approval_audit_evidence_required",
            "approval_rollback_declared",
            "approval_rollback_plan_present",
            "approval_notification_policy_present",
            "certification_eval_gate_passed",
            "certification_cases_present",
            "certification_tool_integrations_present",
            "certification_approval_workflows_present",
            "certification_interpretation_present",
            "pilot_stage_controlled_preview",
            "pilot_target_stage_declared",
            "pilot_blocked_until_prereqs",
            "pilot_minimum_approver_role_present",
            "pilot_readiness_checks_present",
            "pilot_required_evidence_covered",
            "pilot_check_status_required",
            "pilot_check_blocks_production",
            "pilot_check_owner_present",
            "pilot_check_description_present",
            "pilot_controls_present",
            "pilot_controls_read_only_boundary",
            "pilot_controls_draft_only_boundary",
            "connector_pilot_stage_declared",
            "connector_pilot_read_only_first",
            "connector_pilot_approver_present",
            "connector_pilot_connectors_present",
            "connector_access_read_only",
            "connector_required_evidence_complete",
            "connector_forbidden_actions_present",
            "connector_prerequisites_present",
            "connector_controls_no_writes",
            "connector_controls_read_only",
            "connector_controls_pilot_blocked",
            "evidence_capture_stage_declared",
            "evidence_capture_ready",
            "evidence_capture_approver_present",
            "evidence_store_declared",
            "evidence_capture_items_present",
            "evidence_capture_categories_complete",
            "evidence_capture_status_required",
            "evidence_capture_artifacts_present",
            "evidence_controls_tenant_storage",
            "evidence_controls_no_raw_findings",
            "evidence_controls_pilot_blocked",
            "production_pilot_stage_declared",
            "production_pilot_go_no_go_blocked",
            "production_pilot_limited_scope",
            "production_pilot_named_decision",
            "production_pilot_tenant_scope_present",
            "production_pilot_connector_scope_present",
            "production_pilot_action_scope_gated",
            "production_pilot_required_criteria_present",
            "production_pilot_criterion_blocks",
            "production_pilot_controls_blocked",
            "production_pilot_controls_read_only",
            "production_pilot_controls_draft_only"
        ],
    }

    EVIDENCE_DIR.mkdir(exist_ok=True)
    (EVIDENCE_DIR / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (EVIDENCE_DIR / "scorecard.md").write_text(render_scorecard(summary), encoding="utf-8")

    print(f"Gate: {summary['gate']}")
    for result in results:
        status = "ok" if result["passed"] else "fail"
        print(f"  [{status}] {result['caseId']} ({result['lane']})")
        for failure in result["failures"]:
            print(f"       - {failure['name']}: {failure['detail']}")
    if integration_failures:
        print("  [fail] tool integrations")
        for failure in integration_failures:
            print(f"       - {failure['name']}: {failure['detail']}")
    else:
        print(f"  [ok] tool integrations ({summary['toolIntegrationCount']})")
    if approval_failures:
        print("  [fail] approval workflows")
        for failure in approval_failures:
            print(f"       - {failure['name']}: {failure['detail']}")
    else:
        print(f"  [ok] approval workflows ({summary['approvalWorkflowCount']})")
    if certification_failures:
        print("  [fail] certification evidence")
        for failure in certification_failures:
            print(f"       - {failure['name']}: {failure['detail']}")
    else:
        print("  [ok] certification evidence")
    if pilot_failures:
        print("  [fail] pilot readiness")
        for failure in pilot_failures:
            print(f"       - {failure['name']}: {failure['detail']}")
    else:
        print(f"  [ok] pilot readiness ({summary['pilotReadinessCheckCount']})")
    if connector_failures:
        print("  [fail] connector pilot")
        for failure in connector_failures:
            print(f"       - {failure['name']}: {failure['detail']}")
    else:
        print(f"  [ok] connector pilot ({summary['connectorPilotCount']})")
    if evidence_failures:
        print("  [fail] pilot evidence")
        for failure in evidence_failures:
            print(f"       - {failure['name']}: {failure['detail']}")
    else:
        print(f"  [ok] pilot evidence ({summary['pilotEvidenceCaptureCount']})")
    if production_pilot_failures:
        print("  [fail] production pilot")
        for failure in production_pilot_failures:
            print(f"       - {failure['name']}: {failure['detail']}")
    else:
        print(f"  [ok] production pilot ({summary['productionPilotCriteriaCount']})")
    return 0 if not all_failures else 1


def render_scorecard(summary: dict) -> str:
    lines = [
        "# AI Security Control Tower Eval Scorecard",
        "",
        f"**Gate result:** {summary['gate']}",
        "",
        "| Case | Lane | Result |",
        "| --- | --- | --- |",
    ]
    for result in summary["results"]:
        lines.append(f"| {result['caseId']} | {result['lane']} | {'PASS' if result['passed'] else 'FAIL'} |")
    lines.extend([
        "",
        "## Safe tool integrations",
        "",
        f"- Tool integration contracts: `{summary.get('toolIntegrationCount', 0)}`",
        f"- Integration contract result: `{'PASS' if not summary.get('toolIntegrationFailures') else 'FAIL'}`",
        "",
        "## Approval-gated automation",
        "",
        f"- Approval workflow contracts: `{summary.get('approvalWorkflowCount', 0)}`",
        f"- Approval workflow result: `{'PASS' if not summary.get('approvalWorkflowFailures') else 'FAIL'}`",
        "",
        "## Certification-ready evidence",
        "",
        f"- Certification evidence result: `{'PASS' if not summary.get('certificationEvidenceFailures') else 'FAIL'}`",
        "",
        "## Production pilot readiness",
        "",
        f"- Pilot readiness checks: `{summary.get('pilotReadinessCheckCount', 0)}`",
        f"- Pilot readiness result: `{'PASS' if not summary.get('pilotReadinessFailures') else 'FAIL'}`",
        "",
        "## Live connector pilot",
        "",
        f"- Connector pilot contracts: `{summary.get('connectorPilotCount', 0)}`",
        f"- Connector pilot result: `{'PASS' if not summary.get('connectorPilotFailures') else 'FAIL'}`",
        "",
        "## Pilot evidence capture",
        "",
        f"- Pilot evidence capture items: `{summary.get('pilotEvidenceCaptureCount', 0)}`",
        f"- Pilot evidence capture result: `{'PASS' if not summary.get('pilotEvidenceFailures') else 'FAIL'}`",
        "",
        "## Production pilot enablement",
        "",
        f"- Go/no-go criteria: `{summary.get('productionPilotCriteriaCount', 0)}`",
        f"- Production pilot enablement result: `{'PASS' if not summary.get('productionPilotFailures') else 'FAIL'}`",
        "",
        "## Blocking checks",
        "",
        *[f"- `{check}`" for check in summary["blockingChecks"]],
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
