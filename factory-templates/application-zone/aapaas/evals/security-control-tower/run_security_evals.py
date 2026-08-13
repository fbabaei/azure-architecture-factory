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


def main() -> int:
    schema = load_json(SCHEMA_PATH)
    cases = load_json(CASES_PATH)
    tool_integrations = load_json(TOOL_INTEGRATIONS_PATH)
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

    summary = {
        "gate": "PASS" if not all_failures else "FAIL",
        "caseCount": len(cases),
        "passedCount": len([item for item in results if item["passed"]]),
        "failedCount": len([item for item in results if not item["passed"]]),
        "toolIntegrationCount": len(tool_integrations.get("readOnlySources", [])) + len(tool_integrations.get("draftOnlyOutputs", [])),
        "toolIntegrationFailures": integration_failures,
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
            "output_forbidden_actions_explicit"
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
        "## Blocking checks",
        "",
        *[f"- `{check}`" for check in summary["blockingChecks"]],
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
