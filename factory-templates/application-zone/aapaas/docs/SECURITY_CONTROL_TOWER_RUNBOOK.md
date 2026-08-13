# AI Security Control Tower operations runbook

## Purpose

Operate the AI Security Control Tower as a governed security-agent control plane for Red, Blue, Green, and Orchestrator work. The service is certification-ready for controlled preview use with read-only inputs, draft-only outputs, and named-human approval gates.

## Operating boundaries

- No autonomous destructive action.
- No production exploit execution.
- No unapproved containment.
- No automatic pull-request merge.
- No external communication without approved generic wording and named-human approval.
- Security findings, telemetry, repository data, and remediation artifacts stay inside approved tenant systems and evidence stores.

## Daily checks

1. Confirm `/api/application-zone/security-control-tower/work-board` returns `gate: PASS` and four lanes.
2. Confirm `/api/application-zone/security-control-tower/tool-integrations` returns four read-only sources and four draft-only outputs.
3. Confirm `/api/application-zone/security-control-tower/approval-workflows` returns four sensitive-action workflows.
4. Review the scorecard at `evals/security-control-tower/evidence/scorecard.md`.
5. Review any work item whose approval state is not `requires_human_approval` or `approved_by_human`.

## Approval process

1. Collect minimum evidence for the requested sensitive action.
2. Ask the named approver role listed in `approval-workflows.json` to review evidence, blast radius, and rollback or compensation guidance.
3. Record `approval_requested`, review event, `approval_recorded`, and `action_executed_or_rejected`.
4. Execute only the approved action scope.
5. Record outcome and rollback/compensation review.

## Escalation

- Security incident commander: containment decisions.
- Service owner or change manager: production changes.
- Code owner: pull-request merge.
- Communications owner and legal reviewer: external communications.

## Rollback and compensation

- Containment and production changes require rollback guidance before execution.
- Pull-request merge requires revert strategy and test evidence before merge.
- External communications cannot be rolled back; require pre-send audience validation and approved generic wording.

## Promotion status

Certification-ready controlled preview. Production adoption still requires target-environment connector configuration, managed persistence, tenant-specific RBAC review, and live health evidence capture.
