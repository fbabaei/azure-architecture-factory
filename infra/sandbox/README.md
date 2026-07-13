# Architecture Factory — Sandbox (Phase 1) IaC

Implements Phase 1 of [../../docs/SANDBOX_DESIGN.md](../../docs/SANDBOX_DESIGN.md):
**execution isolation + a bounded Azure target**. This directory is **authoring-only** —
nothing here provisions Azure resources until you run the deploy commands below.

## What this deploys

| File | Purpose |
|---|---|
| `main.bicep` | Subscription-scoped: creates the dedicated sandbox resource group, then deploys the resources below into it. |
| `sandbox-resources.bicep` | RG-scoped: least-privilege managed identity, region-allowlist + require-`expiresOn`-tag policies, monthly budget, isolated Container Apps environment + ephemeral execution Job. |
| `params/sandbox.dev.bicepparam` | Parameter values — **edit before deploying** (emails, budget, regions). |
| `../../scripts/sandbox_ttl_cleanup.ps1` | TTL reaper: deletes sandbox resources whose `expiresOn` tag is in the past. |

Design defaults baked in: **ACA Job**, **dedicated resource group**, **72h TTL** (enforced by the reaper + tag policy), budget alerts at **50/90/100%**.

## Prerequisites

- `az` logged in to the target subscription; Owner or User Access Administrator (policy + role assignments are created).
- The portal ACR (`archfactorydevacr`) exists (the job pulls its image from there).

## 1. Validate (what-if, no changes)

```powershell
az deployment sub what-if `
  --location eastus `
  --template-file infra/sandbox/main.bicep `
  --parameters infra/sandbox/params/sandbox.dev.bicepparam
```

## 2. Deploy

```powershell
az deployment sub create `
  --location eastus `
  --template-file infra/sandbox/main.bicep `
  --parameters infra/sandbox/params/sandbox.dev.bicepparam
```

## 3. Post-deploy (manual, cross-RG)

The execution identity needs **AcrPull** on the portal ACR (which lives in a different RG),
so grant it after deployment using the `executionIdentityPrincipalId` output:

```powershell
$acrId = az acr show --name archfactorydevacr --query id -o tsv
$principalId = "<executionIdentityPrincipalId from the deployment outputs>"
az role assignment create --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
  --role AcrPull --scope $acrId
```

## 4. Schedule TTL cleanup

Run the reaper on a schedule (Container Apps cron job or Azure Automation). Dry run first:

```powershell
pwsh -File scripts/sandbox_ttl_cleanup.ps1 -WhatIf
pwsh -File scripts/sandbox_ttl_cleanup.ps1
```

## Notes & honest limitations

- **Budget = alerts, not a native hard stop.** Azure Consumption budgets notify; the *hard* lifecycle/cost boundary is enforced by the `expiresOn` tag policy + the TTL reaper. A stricter hard stop (auto-disable on budget breach) would be an action group + automation runbook (Phase 2/3).
- **AcrPull is a manual post-step** because it targets a resource group outside this deployment's scope.

## Gated next steps (NOT done here)

These change live behavior / build artifacts and should be done explicitly, in order:

1. **Build the `sandbox-runner` image** — a container with the generation toolchain (Copilot CLI, `azd`, Bicep) that runs one BRD→project generation, tags created resources with `expiresOn`, and writes artifacts/logs out. Push as `archfactorydevacr.azurecr.io/sandbox-runner:latest`.
2. **Rewire the portal backend** (`scripts/start_factory_portal.py`) so generation **dispatches the ACA Job** (start job execution + poll) instead of spawning Copilot in-process, and streams the job's artifacts/logs back to the project view.
3. **Remove deploy rights from the portal identity** (Phase 2) once the job owns deployment.
