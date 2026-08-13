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

## Production pilot readiness

Before production-pilot rollout, confirm:

1. Tenant connector inventory is approved for code scanning, XDR, cloud posture, and repository metadata.
2. RBAC and managed identity review is complete.
3. Managed persistence, retention, backup, and purge plans are approved.
4. Observability dashboard and alerts are published.
5. Live health evidence is captured from the target environment.
6. Rollback and compensation drill is complete.
7. Data retention and sensitivity review is complete.

The pilot-readiness contract at `evals/security-control-tower/pilot-readiness.json` intentionally keeps `overallStatus` blocked until these prerequisites are complete.

## Live connector pilot preparation

The connector pilot contract at `evals/security-control-tower/connector-pilot.json` defines the first read-only connector set:

- GitHub code scanning
- Defender/XDR summary
- Cloud posture summary
- Repository metadata

Each connector requires tenant inventory, RBAC review, sample read-only query evidence, and audit-log mapping before activation. No connector writes are allowed during the initial pilot.
