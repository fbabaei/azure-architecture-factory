# Compliance Agent certification report

## Status

Candidate with strong implementation evidence.

## Evidence

| Area | Evidence |
| --- | --- |
| Source repo | `C:\dev\workspace\compliance-agent` |
| Manifest | `app-packs\compliance-agent\0.1.0\manifest.json` |
| Architecture | `README.md` and `docs\Architecture-Diagram-v3.md` describe Angular UI, ASP.NET Core API, Foundry Responses, RAG, SQLite persistence, HITL extraction lifecycle, and audit/history tables |
| Health | `src\ComplianceAgent.Api\Program.cs` maps `/health` |
| Deployment | `docs\ACA-Deployment.md` covers Azure Container Apps deployment, managed identity, ACR, Foundry access, and verification |
| Security | Deployment guide emphasizes system-assigned managed identity and no API keys for Foundry access |
| Verification | Repo contains `tests`, smoke scripts are described in README, and manifest maps verification to smoke and HITL lifecycle scripts |

## Gaps to close before certification

1. Add or confirm versioned infrastructure-as-code in the repo export path, not only manual CLI deployment guidance.
2. Add a formal rollback runbook or rollback section for ACA deployment.
3. Add an app-pack-specific starter eval plan under the source repo or service eval catalog.
4. Confirm Key Vault usage for all production secrets and document required secret names.
5. Generate dev/test/prod deployment parameters through the service tools.

## Recommended next action

Promote this to `preview` after IaC, rollback, Key Vault, and eval artifacts are complete.
