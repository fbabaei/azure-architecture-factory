# 🧭 Guide Report — order-management-platform

_Generated at **2026-04-16T02:59:41.262195Z** by the factory guide report generator (deterministic, no LLM). Regenerate any time by re-running `scripts/generate_guide_report.py` or by clicking **🧭 Guide Me → Refresh**._

## Snapshot

- **Project slug:** `order-management-platform`
- **Status (manifest):** `unknown`
- **Network tier:** `unknown`  **Observability:** `False`
- **Findings:** 🔴 1 critical · 🟠 0 warning · 🟡 0 advisory · ✅ 1 ok

## 🔴 Critical

### Bicep validation (Phase 3) has not run

No `logs/phase-3-infra-validation.log` exists. Run the `bicep-infrastructure-validator` agent before deploying.

Related: `logs/phase-3-infra-validation.log`

## ✅ Looking good

### Architecture diagram present

A `.drawio` diagram exists in `diagrams/`.

Related: `diagrams/`

## ✅ What to do next

1. **Run agent `bicep-infrastructure-validator`** — Catch Bicep syntax/logic errors before deploy.
   - Arguments: `project-path: projects/order-management-platform`

---

> This report is a static snapshot. For a live analysis that reads current file content, open the project in VS Code Desktop or vscode.dev and run the `factory-workflow-guide` agent in Copilot Chat.
