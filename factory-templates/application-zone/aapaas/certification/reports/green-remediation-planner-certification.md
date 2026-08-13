# Green Remediation Planner AgentPack certification

## Status

`certification-ready`

## Summary

Drafts hardening guidance, remediation plans, runbook updates, and optional pull requests for human review.

## Certification evidence

- Draft-only remediation contract is represented by `green-remediation-pr`.
- Human-review-required policy is enforced by `approval-workflows.json`.
- Rollback guidance is required for production change and pull-request merge workflows.
- Audit trail requirements are part of the approval workflow contract.
- Eval checks prove no automatic merge or production deployment.

## Certification note

This AgentPack is certification-ready for controlled preview. It can create draft artifacts but must not merge pull requests or deploy changes without named-human approval.
