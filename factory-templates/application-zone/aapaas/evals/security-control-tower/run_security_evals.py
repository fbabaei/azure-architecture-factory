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


def main() -> int:
    schema = load_json(SCHEMA_PATH)
    cases = load_json(CASES_PATH)
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

    summary = {
        "gate": "PASS" if not all_failures else "FAIL",
        "caseCount": len(cases),
        "passedCount": len([item for item in results if item["passed"]]),
        "failedCount": len([item for item in results if not item["passed"]]),
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
            "approved_by_named_human"
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
        "## Blocking checks",
        "",
        *[f"- `{check}`" for check in summary["blockingChecks"]],
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
