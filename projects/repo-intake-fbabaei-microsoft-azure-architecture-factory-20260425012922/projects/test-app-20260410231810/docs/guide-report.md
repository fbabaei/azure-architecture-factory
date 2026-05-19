# 🧭 Guide Report — Test App

_Generated at **2026-04-16T02:59:41.626694Z** by the factory guide report generator (deterministic, no LLM). Regenerate any time by re-running `scripts/generate_guide_report.py` or by clicking **🧭 Guide Me → Refresh**._

## Snapshot

- **Project slug:** `test-app-20260410231810`
- **Status (manifest):** `complete`
- **Network tier:** `unknown`  **Observability:** `False`
- **Findings:** 🔴 3 critical · 🟠 2 warning · 🟡 1 advisory · ✅ 1 ok

## 🔴 Critical

### infra/main.bicep is a starter placeholder, not a real implementation

The Bicep file is a scaffold and `infra/modules/` is empty. Run `azure-architecture-implementer` to emit per-service Bicep modules that match the diagram.

Related: `infra/main.bicep`, `infra/modules/`

### Bicep validation (Phase 3) has not run

No `logs/phase-3-infra-validation.log` exists. Run the `bicep-infrastructure-validator` agent before deploying.

Related: `logs/phase-3-infra-validation.log`

### Production readiness review (Phase 4) has not run

No `docs/production-checklist.md` exists. Run the `production-environment-advisor` agent to confirm production gates (identity, secrets, networking, monitoring, RBAC).

Related: `docs/production-checklist.md`

## 🟠 Warnings

### Manifest says status=complete but phases 3 and 4 are missing

Reset `status` in `project-manifest.json` to `in-progress` until validation and production review complete.

Related: `project-manifest.json`

### Only starter service scaffold exists under src/

The starter runner emits one `copilot_api` service. If your diagram lists multiple services, run `azure-architecture-implementer` to scaffold each component.

Related: `src/`

## 🟡 Advisory

### A duplicate copy exists under your user home

`C:\Users\fbabaei\app\test-app-20260410231810` was created by the starter runner. It will drift from the workspace copy after regeneration. Treat the workspace project as the source of truth.

Related: `C:\Users\fbabaei\app\test-app-20260410231810`

## ✅ Looking good

### Architecture diagram present

A `.drawio` diagram exists in `diagrams/`.

Related: `diagrams/`

## ✅ What to do next

1. **Run agent `azure-architecture-implementer`** — Regenerate infra + services so they match the BRD and diagram.
   - Arguments: `project-path: projects/test-app-20260410231810`, `networkTier: private`, `enableObservability: True`
2. **Run agent `bicep-infrastructure-validator`** — Catch Bicep syntax/logic errors before deploy.
   - Arguments: `project-path: projects/test-app-20260410231810`
3. **Run agent `production-environment-advisor`** — Confirm identity, secrets, networking, and monitoring gates.
   - Arguments: `project-path: projects/test-app-20260410231810`

---

> This report is a static snapshot. For a live analysis that reads current file content, open the project in VS Code Desktop or vscode.dev and run the `factory-workflow-guide` agent in Copilot Chat.
