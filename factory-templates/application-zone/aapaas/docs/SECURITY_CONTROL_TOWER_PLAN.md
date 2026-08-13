# AI Security Control Tower phased plan

This plan applies Red/Blue/Green security-agent patterns to AI Factory Services without granting autonomous destructive authority.

## Phase 1: Catalog and governance baseline

- Add `AI Security Control Tower` as a candidate AppPack.
- Add candidate AgentPacks for:
  - Security Playbook Orchestrator
  - Red Exploitability Validator
  - Blue Detection Generator
  - Green Remediation Planner
- Define data boundaries, approval gates, tool contracts, and certification criteria.
- Keep all runtime actions in recommend/draft/evidence mode.

## Phase 2: Evidence and eval harness

- Define a security evidence schema for exploitability, detection, remediation, approval, and closure.
- Add sample findings and playbook fixtures.
- Add evals proving:
  - no production containment without approval
  - no PR merge without approval
  - no destructive exploit execution
  - evidence is produced for every recommendation

Phase 2 starter artifacts:

- `evals/security-control-tower/evidence-schema.json`
- `evals/security-control-tower/cases.json`
- `evals/security-control-tower/run_security_evals.py`
- `evals/security-control-tower/README.md`

## Phase 3: Portal work board

- Add a security work-board view to AI Apps & Agents as a Service.
- Show work status by Red, Blue, and Green lane.
- Track evidence, owner, approval state, and next action.
- Add exportable readiness/certification evidence.

Phase 3 portal surface:

- `GET /api/application-zone/security-control-tower/work-board`
- Renders the Security Work Board in the AI Apps & Agents as a Service workspace.
- Uses the Phase 2 eval cases and generated PASS scorecard as the initial board data.
- Displays approval-required actions explicitly so containment, production changes, PR merge, and external notifications remain human-gated.

## Phase 4: Safe tool integrations

- Integrate read-only sources first:
  - code scanning findings
  - Defender/XDR telemetry summaries
  - cloud posture findings
  - repository metadata
- Add draft-only outputs:
  - detection drafts
  - remediation plans
  - draft pull requests
  - runbook updates

Phase 4 starter surface:

- `GET /api/application-zone/security-control-tower/tool-integrations`
- `evals/security-control-tower/tool-integrations.json`
- The eval gate now verifies source integrations are `read_only`, output integrations are `draft_only`, and every sensitive promotion requires named human approval.
- The portal renders safe integration cards beside the Security Work Board so source boundaries, allowed outputs, and forbidden sensitive actions are visible before runtime tool activation.

## Phase 5: Approval-gated automation

- Add named-human approval workflows for containment, production changes, PR merge, and external communications.
- Store audit events for every approval and action.
- Add rollback/compensation guidance.

Phase 5 starter surface:

- `GET /api/application-zone/security-control-tower/approval-workflows`
- `evals/security-control-tower/approval-workflows.json`
- The eval gate now verifies every sensitive action has an `approval_gated` workflow, named human approval, required evidence, audit events, and rollback or compensation guidance.
- The portal renders Approval Gates cards so approver role, evidence requirements, audit trail, rollback plan, and notification policy are visible before any sensitive action is enabled.

## Phase 6: Certification-ready promotion

Promotion completed after:

- runtime health is captured
- eval suite passes
- security data boundaries are reviewed
- approval gates are proven
- work-board evidence is persisted
- operations runbook is complete

Phase 6 evidence:

- Parent AppPack `ai-security-control-tower` promoted to `preview` with `standard` support tier and `certification-ready` summary status.
- Security AgentPacks promoted to `certification-ready` for controlled preview:
  - Security Playbook Orchestrator
  - Red Exploitability Validator
  - Blue Detection Generator
  - Green Remediation Planner
- Certification evidence captured in `operations/health/ai-security-control-tower-certification.generated.json`.
- Runtime control-plane baseline captured in `operations/instances/ai-security-control-tower-dev-eastus.instance.json`.
- Operations runbook published at `docs/SECURITY_CONTROL_TOWER_RUNBOOK.md`.

## Non-goals

- No autonomous destructive action.
- No production exploit execution.
- No unapproved containment.
- No automatic PR merge.
- No customer-facing use of source-specific roadmap or timing details.
