# Supply Chain Control Tower certification report

## Status

Certification-ready seed pack.

## Evidence

| Area | Evidence |
| --- | --- |
| Source repo | `C:\dev\workspace\supply-chain-control-tower` |
| Manifest | `app-packs\supply-chain-control-tower\0.1.0\manifest.json` |
| Architecture | `README.md` and `docs\diagrams` describe a multi-agent control tower with deterministic engines and human approval gates |
| Deployment | `azure.yaml` defines a Foundry hosted agent and AI project deployment through `azd` |
| Offline validation | `docs\quick-start.md` documents offline walkthrough, tests, and eval gate |
| Human approval | README/quick-start state that no material order is automatically committed and every commit is owned by a named human |
| Verification | `python -m pytest tests -q` passed 162 tests; `python evals\run_evals.py` returned Gate: PASS |
| Operations evidence | `operations\instances\supply-chain-control-tower-dev-eastus.instance.json`, `operations\health\supply-chain-control-tower-dev-eastus.health.generated.json`, and `operations\health\supply-chain-control-tower-eval.generated.json` capture readiness evidence |

## Certification basis

1. Deterministic planning core is covered by 162 passing tests across demand, supply, inventory, supplier risk, scenarios, approvals, ERP adapters, profiles, portal, and ranking.
2. Eval gate passed all 17 blocking checks, including no auto-commit, approval queue threshold, no committed orders after plan, approval-required orders pending, audit trail completeness, supplier risk range/roll-up consistency, and scenario safety.
3. Advisory KPI gaps are surfaced as planning signals, not certification blockers. The eval report intentionally flags fill-rate and inventory-turn issues as business conditions for planner action.
4. Human approval boundary is explicit: no material order is silently committed, and every approval/rejection/commit requires a named human actor.
5. ERP integration is read-only by design until controlled writeback is added; live ERP adapters are configurable by environment and documented in `docs\erp-connectors.md`.
6. Production adoption and day-2 operations are documented in `docs\production-plan.md`, including identity, authorization, managed persistence, telemetry, backups, runbooks, and controlled ERP writeback sequencing.

## Remaining post-certification follow-up

1. Capture deployed Foundry hosted-agent endpoint metadata after target-environment deployment.
2. Replace the certified offline/dev baseline instance record with live hosted-agent health and sample invocation evidence when available.
3. Add managed persistence and enterprise identity controls before a multi-user production pilot.
4. Add controlled ERP writeback only after read-only data mapping, authorization, audit, and reconciliation are proven.
