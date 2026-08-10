# Mailer Automation certification report

## Status

Candidate with strong workflow and deployment evidence; security hardening required before certification.

## Evidence

| Area | Evidence |
| --- | --- |
| Source repo | `C:\dev\workspace\Mailer-Automation` |
| Manifest | `app-packs\mailer-automation\0.1.0\manifest.json` |
| Architecture | `README.md` and `documents\ReadMe-Deployment.md` describe OCR, vision AI, policy-aware RAG analysis, human review, audit trail, and multi-facility support |
| Local deployment | `Docker\README.md` describes Docker Compose startup for digitization agent, content-analysis agent, API, and Angular frontend |
| Azure deployment | `Infra\deploy.ps1` provisions resource group, Bicep, ACR, Container Apps, RBAC, image builds, and service URLs |
| Health | `api\src\main.py` exposes `/api/health` |
| Human review | README and deployment docs require officer review for decisions |

## Gaps to close before certification

1. `Infra\deploy.ps1` enables ACR admin credentials; replace with managed-identity image pull for production certification.
2. Confirm Key Vault integration for all production configuration and secrets.
3. Add formal smoke test scripts that can run after deployment.
4. Add rollback runbook and deployment rollback mechanics.
5. Add starter eval plan for OCR quality, policy retrieval quality, safety, and human-review correctness.
6. Normalize folder naming and service layout in the app-pack export contract.

## Recommended next action

Keep as `candidate` and prioritize security hardening around ACR credentials, Key Vault, and production deployment identity.
