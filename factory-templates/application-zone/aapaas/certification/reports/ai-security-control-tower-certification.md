# AI Security Control Tower certification report

## Status

`candidate-with-gaps`

## Certification decision

AI Security Control Tower is approved for inclusion in the governed AAPAAS catalog as a candidate `AppPack`.

The pack captures a reusable Red/Blue/Green security-agent pattern for investigation, validation, detection drafting, and remediation planning. It is intentionally not certification-ready until runtime contracts, test/eval fixtures, work-board evidence, and approval-gated tool integrations are implemented.

## Evidence source

This candidate is derived from internal security-agent design guidance about defending at AI speed using coordinated Red, Blue, and Green agents.

Use only the generalized Red/Blue/Green pattern in catalog and customer-facing artifacts:

- Red agents validate exposure and exploitability.
- Blue agents triage, detect, and respond.
- Green agents harden posture and draft remediation.
- Orchestration selects playbooks, routes work, and records evidence.
- Destructive or externally visible action remains human-approved.

## Candidate scope

| Area | Candidate behavior |
| --- | --- |
| Red | Non-destructive exploitability validation and prioritization evidence |
| Blue | Detection hypotheses, triage guidance, containment recommendations |
| Green | Remediation plans, hardening guidance, draft pull requests |
| Orchestration | Playbook routing, agent work board, evidence capture, approval gates |

## Required certification evidence

1. Tool contracts for every Red/Blue/Green action.
2. Explicit data-boundary statement for findings, telemetry, code, and remediation artifacts.
3. Human approval gate for containment, production changes, pull-request merge, or external communication.
4. Audit trail for playbook selection, agent work, evidence, approvals, and outcomes.
5. Eval suite proving no destructive action is taken without approval.
6. Evidence schema for exploitability, detection, remediation, and closure.
7. Runtime health/readiness evidence for the work board and agent endpoints.

## Phase 2 evidence harness

The Phase 2 offline eval gate is available at:

`factory-templates/application-zone/aapaas/evals/security-control-tower/run_security_evals.py`

It validates candidate evidence envelopes, Red/Blue/Green lane classification, approval requirements, and the no-autonomous-destructive-action contract before runtime integrations are built.

## Phase 3 portal work board

The Phase 3 portal surface exposes the offline evidence as a visible Security Work Board:

`GET /api/application-zone/security-control-tower/work-board`

The board renders Orchestrator, Red, Blue, and Green lanes in the AI Apps & Agents as a Service workspace and shows each work item's request, playbook, risk, evidence types, action modes, eval result, and human-approval gates.

## Phase 4 safe tool integrations

The Phase 4 starter contract is available at:

`factory-templates/application-zone/aapaas/evals/security-control-tower/tool-integrations.json`

The portal exposes it through:

`GET /api/application-zone/security-control-tower/tool-integrations`

The eval gate now blocks any source that is not `read_only`, any output that is not `draft_only`, and any sensitive promotion path that lacks human approval. The visible portal cards list read-only source boundaries, draft-only outputs, and forbidden actions for code scanning findings, Defender/XDR summaries, cloud posture findings, repository metadata, detection drafts, remediation plans, draft pull requests, and runbook updates.

## Phase 5 approval-gated automation

The Phase 5 starter contract is available at:

`factory-templates/application-zone/aapaas/evals/security-control-tower/approval-workflows.json`

The portal exposes it through:

`GET /api/application-zone/security-control-tower/approval-workflows`

The eval gate now verifies that containment, production changes, pull-request merge, and external communication each have an `approval_gated` workflow with a named human approver role, minimum evidence requirements, audit events, rollback or compensation guidance, and a notification policy. The visible Approval Gates cards make these requirements reviewable before sensitive actions are enabled.

## Promotion criteria

Move to `certification-ready` only after:

- Red, Blue, and Green AgentPacks each pass contract and safety evals.
- Security Playbook Orchestrator can route a request and produce a complete evidence record.
- Draft PR and containment paths are explicitly approval-gated.
- Work-board state and audit evidence are persisted.
- Documentation explains operational ownership, escalation, and rollback.
