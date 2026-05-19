# MDR Support — Production Readiness

This document evaluates whether the MDR support project can be deployed
to Azure as-is and enumerates the changes required for a production-grade
deployment.

## Short answer

The project deploys cleanly to Azure for **dev / POC** with one command
(`az deployment group create -f infra/main.bicep`). It needs the changes
below before it is suitable for **production traffic**.

## What works out-of-the-box

Running `infra/main.bicep` provisions a functioning end-to-end stack:

- Container Apps (FastAPI, scale 1–3), APIM with JWT policy hook, Azure
  OpenAI (`gpt-5.2` chat + `text-embedding-3-small` embeddings),
  Document Intelligence, AI Search, Cosmos DB (four containers: `arrangements`,
  `sessions`, `case-drafts`, `audit-log`), Blob Storage (`mdr-documents` +
  `knowledge-base-source`), Key Vault, Log Analytics + Application Insights,
  and a user-assigned managed identity.
- `disableLocalAuth: true` on OpenAI, Document Intelligence, and Cosmos.
- APIM rate-limit policy (60/min) and optional JWT validation when an
  `apiAudience` parameter is supplied.
- Microsoft Agent Framework runtime is **opt-in** via
  `AGENT_FRAMEWORK_ENABLED=1`. When disabled (default), the deterministic
  local runtime is used. Either path is production-safe — the framework is
  **not** a deployment blocker.

## What must change before production

| # | Gap | Where | Severity | Fix |
|---|-----|-------|----------|-----|
| 1 | Container image is a placeholder (`mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`). | `infra/main.bicep` `containerImage` default | Blocker | Build from project `Dockerfile`, push to ACR, pass `--parameters containerImage=<acr>.azurecr.io/mdr-agent:<tag>`. Recommended: provision ACR in the same Bicep and grant the MI `AcrPull`. |
| 2 | Cosmos RBAC role is declared as an ARM role assignment, but Cosmos data-plane access requires `Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments`. The current assignment deploys without error but does not actually grant data access. | `infra/main.bicep` `cosmosRoleAssignment` | Blocker | Replace with a `sqlRoleAssignments` resource using role definition `00000000-0000-0000-0000-000000000002` (Built-in Data Contributor) scoped to the account. |
| 3 | `DEPLOY.md` still tells operators to assign RBAC roles manually. | `DEPLOY.md` "Grant managed identity access" section | Medium | Remove manual step; point to the Bicep-managed assignments. |
| 4 | Public network on every data and AI service (`publicNetworkAccess: 'Enabled'`), Container App ingress external. | All resources in `infra/main.bicep` | High (prod) | Phase 2: VNet-integrated Container Apps environment, private endpoints for Cosmos, Blob, Key Vault, OpenAI, Document Intelligence, AI Search. Restrict Key Vault / Storage firewalls. |
| 5 | APIM Developer SKU — no SLA. | `infra/main.bicep` `apim.sku` | High (prod) | Change to `Basic`, `Standard`, or `Premium` (Premium if VNet integration is required). |
| 6 | JWT validation is optional and off when `apiAudience` is empty. | `apimPolicyXml` branch in `main.bicep` | High (prod) | Set `apiAudience` to the Entra app audience in every non-dev environment. Enforce via CI parameter gate. |
| 7 | Cosmos: no continuous backup, no zone redundancy, single region. | `cosmos` resource in `main.bicep` | High (prod) | Add `backupPolicy: { type: 'Continuous' }`, set `isZoneRedundant: true`, decide on geo-replication. |
| 8 | Key Vault: soft-delete only, no purge protection. | `keyVault` resource | Medium | Set `enablePurgeProtection: true` for prod. |
| 9 | No metric alerts defined. Action group is created only when `operationsEmail` is set. | `main.bicep` observability block | Medium | Add alerts: Container App replica failures, OpenAI 429s, Cosmos 429s, APIM 5xx. Wire to the action group. |
| 10 | AI Search index schema is created by a post-deploy script, not by Bicep. | `scripts/run_search_index.ps1` | Low | Keep as CI step, or add an `azcli` deployment script resource that calls `scripts/bootstrap_search_index.py`. |
| 11 | If Agent Framework is enabled (`AGENT_FRAMEWORK_ENABLED=1`), the MI also needs **Azure AI Developer** on a Foundry project, which is not provisioned in this Bicep. | Deployment-time decision | Low | Either leave the framework disabled in prod (local runtime is prod-safe) or add a Foundry project + role assignment. |

## Is the Microsoft Agent Framework a problem?

No. It is wrapped in `src/mdr_agent/services/agent_runtime.py` with a
graceful fallback (`foundry_agent_runtime.py`). If the SDK is not
installed or Foundry settings are missing, it logs a warning and falls
back to a deterministic in-process implementation. You can ship to
production with `AGENT_FRAMEWORK_ENABLED` unset and API behaviour is
identical to the framework path.

## Recommended promotion path

- **Dev / POC today:** deploy as-is after fixing #1 (real container image)
  and #2 (Cosmos data-plane RBAC). Everything else is already functional.
- **Before production traffic:** additionally fix #3, #5, #6, #9 (docs,
  APIM SKU, JWT on, alerts).
- **Before regulated or customer-facing production:** additionally fix
  #4, #7, #8, #10 (private networking, Cosmos backup + zone redundancy,
  Key Vault purge protection, Search index automation).

## Related files

- `infra/main.bicep` — IaC source of truth.
- `DEPLOY.md` — deployment runbook.
- `docs/architecture-overview.md` — architecture alignment with the
  Compliance Intelligence Agent Technical Design reference.
- `docs/detailed-architecture.md` — component-level view.
