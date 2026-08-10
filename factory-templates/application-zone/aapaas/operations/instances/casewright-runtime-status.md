# CaseWright runtime status

## Current status

CaseWright is registered as the first AAPAAS managed instance and has a healthy API/worker runtime.

| Component | Azure resource | Status |
| --- | --- | --- |
| API | `casewright-api` Container App | Running |
| Worker | `casewright-worker` Container App | Running |
| Scheduler Function | `casewright-scheduler-zhauoubl` Function App | Provisioned, package deployment blocked by storage public network policy |
| Scheduler Job | `casewright-sync-scheduler` Container Apps Job | Created, scheduled every 6 hours, execution succeeds |

## Endpoint

- API base URL: `https://casewright-api.bluesand-957fb9f7.eastus2.azurecontainerapps.io`
- Health: `https://casewright-api.bluesand-957fb9f7.eastus2.azurecontainerapps.io/api/health`
- Docs: `https://casewright-api.bluesand-957fb9f7.eastus2.azurecontainerapps.io/docs`

## Notes

The original `dev-eastus` environment was blocked by East US Cosmos DB capacity. The working runtime is now in the `dev` environment:

- Resource group: `rg-dev`
- Region: `eastus2`
- Search region override: `eastus`

The scheduler Function App package deployment is still pending because `azd deploy casewright-scheduler` cannot upload the package to the Function App deployment storage account while public network access is disabled by policy. A Container Apps scheduled job has been created as a policy-compatible workaround. Its target now succeeds and returns `queued: 0` with `status: skipped` when SharePoint/Graph is unavailable or not configured.
