# AAPAAS todo list

## Current priority

1. [x] Register the existing CaseWright Azure resources as the first AAPAAS managed instance.
2. [x] Create an instance inventory under `operations\instances`.
3. [x] Validate CaseWright runtime health.
   - API and worker are running in `rg-dev`; health checks pass at `/api/health` and `/docs`.
   - Scheduler Function App package deployment remains pending.
4. [x] Tighten certification gates so app packs require deployment evidence, runtime health evidence, rollback evidence, and security evidence before promotion.
5. [ ] Prepare the AAPAAS pilot package: service brief, intake form, demo script, success metrics, and 30/60/90 rollout.

## Recommended next engineering action

Complete or redeploy the CaseWright runtime services against the discovered infrastructure, then update:

- `operations\instances\casewright-dev-eastus.instance.json`
- `runtime.apiContainerApp`
- `runtime.workerContainerApp`
- `runtime.apiBaseUrl`

After that, run:

```powershell
.\scripts\Test-AppInstanceHealth.ps1 -InstanceId casewright-dev-eastus
```

## Candidate pack work

| Pack | Next action |
| --- | --- |
| Compliance Agent | Add/confirm IaC, rollback runbook, Key Vault production mapping, and app-pack eval plan. |
| Supply Chain Control Tower | Certified baseline complete; next capture live hosted-agent endpoint evidence after target deployment. |
| Mailer Automation | Replace ACR admin credentials with managed identity, add smoke tests, rollback, and eval plan. |
