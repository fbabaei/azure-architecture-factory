# CaseWright scheduler status

## Current result

A policy-compatible scheduled job has been created:

- Resource group: `rg-dev`
- Job: `casewright-sync-scheduler`
- Trigger: schedule
- Cron: `0 */6 * * *`
- Target: `POST https://casewright-api.bluesand-957fb9f7.eastus2.azurecontainerapps.io/api/sharepoint/sites/sync`

This avoids the Function App zip-deployment blocker caused by storage public network access being disabled by policy.

## Current behavior

The scheduler target is callable and the Container Apps Job execution succeeds.

Because this tenant does not have SharePoint Online available/configured for CaseWright, the API returns:

```json
{"queued":0,"status":"skipped","reason":"sharepoint_unavailable_or_not_configured"}
```

## Remaining production configuration

- `GRAPH_TENANT_ID` is empty
- `GRAPH_CLIENT_ID` is empty

Configure these values and Graph permissions when running against a real SharePoint tenant.

## Next fix

Configure Graph app registration values for the CaseWright API and worker, assign the required Microsoft Graph application permissions, then redeploy the API/worker or restart the Container Apps.

After configuration, run:

```powershell
.\scripts\Test-CaseWrightScheduler.ps1
```
