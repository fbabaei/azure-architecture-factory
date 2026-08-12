# AAPAAS demo script

## Goal

Show that AAPAAS can register, validate, and operate a real AI app pack using CaseWright as the reference implementation.

## Demo flow

### 1. Show the service workspace

Open:

```powershell
C:\dev\workspace\ai-apps-as-a-service
```

Highlight:

- `catalog\service-catalog.json`
- `app-packs\casewright\1.0.0\manifest.json`
- `governance\APP_PACK_CERTIFICATION_CHECKLIST.md`
- `operations\instances\casewright-dev-eastus.instance.json`

### 2. Show the catalog

Explain that each app pack has a versioned manifest with:

- Metadata
- Required inputs
- Azure service requirements
- Security policies
- Health checks
- Lifecycle rules
- Packaging/export rules

### 3. Show CaseWright as the reference instance

Open:

```powershell
operations\instances\casewright-runtime-status.md
```

Show:

- API Container App is running.
- Worker Container App is running.
- Health checks pass.
- Scheduler package deployment remains the known gap.

### 4. Run health validation

```powershell
.\scripts\Test-AppInstanceHealth.ps1 -InstanceId casewright-dev-eastus
```

Expected result:

- `/api/health` returns 200.
- `/docs` returns 200.

### 5. Show certification status

```powershell
.\scripts\Test-AppPackCertification.ps1
```

Explain:

- CaseWright is the reference pack.
- Compliance Agent and Mailer Automation are candidates.
- Supply Chain Control Tower is certification-ready with offline/dev readiness evidence and human-approval guardrails.
- Candidate gaps are tracked in `certification\reports`.

### 6. Show app-pack export

```powershell
.\scripts\Export-AppPack.ps1 -PackId casewright -Version 1.0.0 -OutputRoot .\outputs\application-zone
```

Explain that app packs can be exported as standalone deployable bundles.

### 7. Close with the operating model

Open:

```powershell
operations\OPERATING_MODEL.md
```

Explain that AAPAAS is not just app generation. It includes managed operation, health, evals, incidents, upgrades, rollback, and continuous improvement.
