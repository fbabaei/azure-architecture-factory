# Security Playbook Orchestrator AgentPack certification

## Status

`certification-ready`

## Summary

Routes security requests to governed Red, Blue, and Green agents and tracks work through an approval-gated evidence board.

## Certification evidence

- Playbook routing eval is captured by `orchestrator-routing` in `evals/security-control-tower/cases.json`.
- Work-board state is exposed through `/api/application-zone/security-control-tower/work-board`.
- Evidence references are rendered in the work board and scorecard.
- Named-human approval capture is specified in `approval-workflows.json`.
- No autonomous destructive action is enforced by the eval gate.

## Certification note

This AgentPack is certification-ready for controlled preview as a governed orchestrator contract. Tenant-specific connector activation still requires RBAC, persistence, and operational ownership review.
