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

## Promotion criteria

Move to `certification-ready` only after:

- Red, Blue, and Green AgentPacks each pass contract and safety evals.
- Security Playbook Orchestrator can route a request and produce a complete evidence record.
- Draft PR and containment paths are explicitly approval-gated.
- Work-board state and audit evidence are persisted.
- Documentation explains operational ownership, escalation, and rollback.
