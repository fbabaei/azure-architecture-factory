# Supply Chain Control Tower certification report

## Status

Candidate with excellent domain logic and evaluation evidence; not yet production-service certified.

## Evidence

| Area | Evidence |
| --- | --- |
| Source repo | `C:\dev\workspace\supply-chain-control-tower` |
| Manifest | `app-packs\supply-chain-control-tower\0.1.0\manifest.json` |
| Architecture | `README.md` and `docs\diagrams` describe a multi-agent control tower with deterministic engines and human approval gates |
| Deployment | `azure.yaml` defines a Foundry hosted agent and AI project deployment through `azd` |
| Offline validation | `docs\quick-start.md` documents offline walkthrough, tests, and eval gate |
| Human approval | README/quick-start state that no material order is automatically committed and every commit is owned by a named human |
| Verification | `tests` and `evals\run_evals.py` exist and are documented |

## Gaps to close before certification

1. Define an operations health/readiness model for the hosted Foundry agent, since there is no conventional HTTP `/health` endpoint.
2. Add production runbook for deployment, rollback, incident triage, and Foundry agent recovery.
3. Add Key Vault and managed identity documentation for production configuration.
4. Map ERP adapter modes into validated app-pack inputs and deployment parameters.
5. Add service-level telemetry and SLO evidence for hosted-agent runtime.

## Recommended next action

Keep as `candidate` until health/readiness and day-2 operations are defined for the Foundry-hosted deployment model.
