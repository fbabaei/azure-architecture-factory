# AI Security Control Tower certification report

## Status

Certification-ready seed pack.

## Certification decision

AI Security Control Tower is approved for inclusion in the governed AAPAAS catalog as a certification-ready controlled-preview `AppPack`.

The pack captures a reusable Red/Blue/Green security-agent pattern for investigation, validation, detection drafting, and remediation planning. The certification-ready baseline covers the governed control plane, work-board evidence, read-only/draft-only tool contracts, named-human approval workflows, and operational runbook. Live tenant security connectors remain read-only/draft-only until target-environment RBAC, persistence, and ownership are configured.

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

## Phase 6 certification-ready evidence

| Area | Evidence |
| --- | --- |
| Eval gate | `evals/security-control-tower/evidence/scorecard.md` shows Gate: PASS |
| Work board | `GET /api/application-zone/security-control-tower/work-board` returns 4 lanes and 4 passing work items |
| Safe tools | `GET /api/application-zone/security-control-tower/tool-integrations` returns 4 read-only source contracts and 4 draft-only output contracts |
| Approval gates | `GET /api/application-zone/security-control-tower/approval-workflows` returns 4 named-human approval workflows |
| Operations runbook | `docs/SECURITY_CONTROL_TOWER_RUNBOOK.md` defines daily checks, approval process, escalation, and rollback/compensation guidance |
| Runtime evidence | `operations/instances/ai-security-control-tower-dev-eastus.instance.json` and `operations/health/ai-security-control-tower-dev-eastus.health.generated.json` capture the certified control-plane baseline |
| Certification snapshot | `operations/health/ai-security-control-tower-certification.generated.json` records the blocking checks and certification interpretation |

## Phase 7 production-pilot readiness

The Phase 7 starter contract is available at:

`factory-templates/application-zone/aapaas/evals/security-control-tower/pilot-readiness.json`

The portal exposes it through:

`GET /api/application-zone/security-control-tower/pilot-readiness`

This gate keeps the service in certification-ready controlled preview while production-pilot prerequisites are completed. The contract requires tenant connector inventory, RBAC review, managed persistence, observability, live health evidence, rollback drill, and data-retention review before production pilot can be unblocked.

## Promotion criteria

This pack was promoted to `certification-ready` after:

- Red, Blue, Green, and Orchestrator AgentPacks passed contract and safety eval evidence.
- Security Playbook Orchestrator routing is represented in the work board and produces a complete evidence record.
- Draft PR, containment, production change, and external communication paths are explicitly approval-gated.
- Work-board state and audit evidence are persisted as deterministic certification evidence.
- Documentation explains operational ownership, escalation, and rollback/compensation.
