# CaseWright certification report

## Status

Certification-ready seed pack.

## Evidence

| Area | Evidence |
| --- | --- |
| Source repo | `C:\dev\workspace\casewright` |
| Manifest | `app-packs\casewright\1.0.0\manifest.json` |
| Deployment | `azure.yaml`, `DEPLOY.md`, `infra\main.bicep`, and AAF-generated deployment parameters/commands in the exported sample bundle |
| Architecture | `docs\architecture-decisions.md` documents RAG, Foundry IQ, Azure AI Search, identity-first security, Container Apps, Functions scheduler, and fallback behavior |
| Security | ADR-8 documents managed identity, data-plane RBAC, no account keys, and local-auth/shared-key restrictions where supported |
| Operations | Manifest declares `/health` and `/health/ready`, SLO targets, upgrade strategy, and rollback support |
| Verification | Manifest declares smoke tests and starter eval plan |

## Certification result

CaseWright is the first certified seed pack for this service scaffold. It should remain the reference implementation for app-pack packaging, deployment, and operations.

## Remaining actions before real production rollout

1. Run deployment in a real dev subscription.
2. Run smoke tests against the deployed API.
3. Run starter evals against a representative SharePoint corpus.
4. Capture deployment run evidence under the service operations history.
