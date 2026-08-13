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

## Phase 3: Portal work board

- Add a security work-board view to AI Apps & Agents as a Service.
- Show work status by Red, Blue, and Green lane.
- Track evidence, owner, approval state, and next action.
- Add exportable readiness/certification evidence.

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

## Phase 5: Approval-gated automation

- Add named-human approval workflows for containment, production changes, PR merge, and external communications.
- Store audit events for every approval and action.
- Add rollback/compensation guidance.

## Phase 6: Certification-ready promotion

Promote only after:

- runtime health is captured
- eval suite passes
- security data boundaries are reviewed
- approval gates are proven
- work-board evidence is persisted
- operations runbook is complete

## Non-goals

- No autonomous destructive action.
- No production exploit execution.
- No unapproved containment.
- No automatic PR merge.
- No customer-facing use of source-specific roadmap or timing details.
