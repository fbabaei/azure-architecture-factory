# Observability Guide

The Azure Architecture Factory includes a built-in observability advisor available on every generated project card via the **📡 Observability** button and in the **🚀 Deploy** modal footer. This guide explains what the advisor does, how to invoke it, and how to interpret its output.

---

## Overview

| Entry Point | Where | When to Use |
|---|---|---|
| **📡 Observability** button on project card | Projects list | After deployment, or to audit a Bicep-only project pre-deployment |
| **📡 Observability** button in Deploy modal footer | 🚀 Deploy modal | Immediately after running the deployment commands |
| Direct Copilot Chat prompt | VS Code Copilot Chat | Any time — re-runnable as the project evolves |

---

## What the Advisor Does

The `project-observability-advisor` agent audits your deployed Azure project across **four observability pillars**:

| Pillar | What is checked |
|---|---|
| **Metrics** | Application Insights component present; CPU/memory metrics flowing to Azure Monitor |
| **Logs** | Log Analytics workspace linked; structured logs reaching the workspace |
| **Traces** | Distributed tracing configured; dependency tracking enabled in App Insights |
| **Alerts** | Alert rules exist for: 5xx spike, high CPU, slow dependencies, container restarts, health probe failures, exception rate, memory pressure |

It then:
1. Inventories your resource group for App Insights, Log Analytics, and Container Apps / Functions / App Service resources
2. Identifies gaps across all four pillars
3. Generates **ready-to-run KQL queries** for the most critical failure modes
4. Optionally produces **Bicep modules** to provision missing alert rules, action groups, or App Insights components
5. Saves a dated report to `projects/<name>/docs/observability-report-<date>.md`

---

## How to Use

### From the portal card

1. Find your project in the **Projects** list
2. Click **📡 Observability** — a toast notification confirms the prompt was copied
3. Open **VS Code Copilot Chat** (`Ctrl+Alt+I`)  
4. Paste the prompt and press Enter
5. The agent runs the full audit and saves the report to your project folder

### From the Deploy modal

1. Click **🚀 Deploy** on a project card
2. After the deployment commands finish, click **📡 Observability** in the modal footer
3. Paste the copied prompt into Copilot Chat

### Directly in Copilot Chat

```
Use project-observability-advisor.
Project path: projects/my-project
Resource group: my-project-dev-rg
```

Optional flags:
```
Log Analytics workspace: my-workspace
Application Insights: my-appinsights
Generate Bicep fixes: true
```

---

## Pre-Deployment vs Post-Deployment

The advisor works in both modes:

| Mode | What happens |
|---|---|
| **Pre-deployment** | Scans Bicep files and flags missing observability resources before anything is deployed |
| **Post-deployment** | Queries live Azure resources, runs KQL queries, and validates data is flowing |

If the project has not been deployed, the report clearly states this and audits the Bicep plan instead.

---

## Understanding the Report

The report (`docs/observability-report-<date>.md`) contains:

### Gap Scorecard

```
✅ Metrics     — App Insights present, CPU/memory telemetry confirmed
✅ Logs        — Log Analytics workspace linked, traces flowing
⚠️  Alerts     — Missing: high CPU alert, memory pressure alert
❌ Traces      — Distributed tracing not configured (no dependency tracking)
```

### KQL Queries Included

The advisor generates queries you can run directly in the Azure Portal or Log Analytics:

| Query | Purpose |
|---|---|
| `requests \| where resultCode >= 500` | Last 24h of 5xx errors |
| `exceptions \| summarize count() by type` | Exception frequency by type |
| `dependencies \| where duration > 2000` | Slow external calls (> 2 seconds) |
| `ContainerAppConsoleLogs_CL \| where Level == "Error"` | Container restart errors |

### Optional Bicep Fixes

If you pass `Generate Bicep fixes: true`, the advisor creates ready-to-apply Bicep modules in `projects/<name>/infra/modules/` for:
- Missing alert rules with action group
- App Insights component (if absent)
- Log Analytics workspace link (if absent)

---

## Re-Running After Changes

The advisor is designed to be re-run at any point. Each run saves a new dated report, so you can track improvement over time:

```
docs/observability-report-2026-04-10.md   ← first audit
docs/observability-report-2026-04-14.md   ← after fixes applied
```

Compare the gap scorecards between runs to confirm issues were resolved.

---

## Relationship to Other Agents

| Agent | How it relates |
|---|---|
| `azure-project-deployer` | Deploys the project; run observability advisor after this |
| `bicep-infrastructure-validator` | Validates Bicep syntax; observability advisor validates Bicep *intent* (are the right resources present?) |
| `project-traceability-advisor` | Checks whether observability *requirements* from the BRD are implemented — complements the technical audit |
| `project-cost-analyzer` | Follows observability audit; identifies cost of Log Analytics retention and alert rule volume |
