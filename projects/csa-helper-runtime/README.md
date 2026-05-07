# csa-helper-runtime

Azure-hosted HTTP runtime that exposes the existing `csa-helper/agent-framework` orchestrator + 9 specialist agents as a stateless REST API, backed by **the existing** Azure OpenAI account `fbfoundrywestus` in `rg-fbabaei-2653` (deployment `gpt-4o`).

> Hosting layer only. Per BRD §7 / FR-3, the upstream agent runtime (`https://github.com/fbabaei/csa-helper`) is vendored verbatim — no business-logic changes.

## Architecture

```
client ──HTTPS──> Container App (UAMI) ──> Azure OpenAI (existing, cross-RG)
                       │
                       ├── Key Vault (aoai-endpoint secret)
                       ├── App Insights (FR-6 custom events)
                       └── ACR (image pull via UAMI)
```

Diagram: [`diagrams/csa-helper-runtime.drawio`](diagrams/csa-helper-runtime.drawio) · Notes: [`diagrams/csa-helper-runtime.md`](diagrams/csa-helper-runtime.md).

## Layout

```
csa-helper-runtime/
├── docs/
│   ├── requirements.md           ← copy of BRD
│   ├── alignment-report.md       ← Phase 2.5 (3 iterations, converged)
│   ├── security/report.md        ← Phase 2.6 (passed, 0 critical / 0 major)
│   ├── error-handling/report.md  ← Phase 2.7 (passed)
│   ├── scalability/report.md     ← Phase 2.8 (passed)
│   └── production-checklist.md   ← Phase 4
├── diagrams/
│   ├── csa-helper-runtime.drawio
│   └── csa-helper-runtime.md
├── src/
│   ├── api/main.py               ← FastAPI wrapper (POST /ask, /health, /health/ready)
│   ├── api/__init__.py
│   ├── requirements.txt
│   └── README.md
├── infra/
│   ├── main.bicep                ← orchestrator template (RG scope)
│   ├── modules/
│   │   ├── compute/{acr,containerappenv,containerapp}.bicep
│   │   ├── identity/managed-identity.bicep
│   │   ├── monitoring/{log-analytics,appinsights}.bicep
│   │   ├── rbac/aoai-role-assignment.bicep   ← cross-RG, EXISTING AOAI
│   │   └── security/keyvault.bicep
│   └── params/dev.bicepparam
├── tests/test_api.py             ← 5 smoke tests, all green
├── Dockerfile                    ← multi-stage, vendors upstream csa-helper
├── DEPLOY.md
├── project-manifest.json
└── logs/orchestration.log
```

## Run locally

```pwsh
cd projects\csa-helper-runtime
git clone https://github.com/fbabaei/csa-helper ..\_csa_helper
$env:CSA_HELPER_ROOT = (Resolve-Path ..\_csa_helper).Path
$env:AZURE_OPENAI_ENDPOINT  = "https://fbfoundrywestus.openai.azure.com/"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
$env:AZURE_OPENAI_API_VERSION = "2024-10-21"
pip install -r src\requirements.txt
uvicorn api.main:app --reload --port 8080 --app-dir src
```

Then:
```pwsh
curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/ask -H "content-type: application/json" `
     -d '{"prompt":"Customer wants a Foundry POC milestone next week"}'
```

## Run tests

```pwsh
python -m pytest projects\csa-helper-runtime\tests -v --tb=short --no-header
```

## Deploy

See [`DEPLOY.md`](DEPLOY.md). Deployment was **not** executed by this orchestrator run (`deploy: false`).

## Azure resource map

| Logical | Resource type | Name pattern | Notes |
|---|---|---|---|
| ACR | `Microsoft.ContainerRegistry/registries` (Basic) | `csahelperruntime<token>` | AcrPull → UAMI |
| Container Apps Env | `Microsoft.App/managedEnvironments` | `csa-helper-runtime-dev-cae` | workspace-attached |
| Container App | `Microsoft.App/containerApps` | `csa-helper-runtime` | public 8080, UAMI, min=0/max=3 |
| Managed Identity | `Microsoft.ManagedIdentity/userAssignedIdentities` | `csa-helper-runtime-dev-id` | single, reused |
| Key Vault | `Microsoft.KeyVault/vaults` | `csahelperrun<token>kv` | RBAC, holds `aoai-endpoint` |
| Log Analytics | `Microsoft.OperationalInsights/workspaces` | `csa-helper-runtime-dev-law` | 30-day retention |
| App Insights | `Microsoft.Insights/components` | `csa-helper-runtime-dev-ai` | workspace-based |
| AOAI (existing) | `Microsoft.CognitiveServices/accounts` | `fbfoundrywestus` (`rg-fbabaei-2653`) | RBAC only — never created |

## Phase results

| Phase | Status |
|---|---|
| 0 — Setup | ✅ |
| 1 — Architecture (diagram + notes) | ✅ |
| 1.5 — Agent tooling | ⏭ skipped (`agents=[]`) |
| 2 — Implementation | ✅ |
| 2.5 — Alignment convergence | ✅ converged (3 iter, 0 gaps) |
| 2.6 — Security gate | ✅ passed (0 critical / 0 major / 1 minor accepted) |
| 2.7 — Error-handling gate | ✅ passed |
| 2.8 — Scalability gate | ✅ passed |
| 3 — Bicep validation (`az bicep build`) | ✅ no errors (1 lint warning, false-positive) |
| 3.7 — Test convergence | ✅ converged (5/5 tests green) |
| 4 — Production review | ✅ no blockers |
| 5 — Deployment | ⏭ NOT requested (`deploy: false`) |

## Relationship to AAF and csa-helper

This project is the **packaging + Azure-delivery layer** for an external agent runtime. Two repos collaborate:

| Repo | Role | What it owns |
|---|---|---|
| [`csa-helper`](https://github.com/fbabaei/csa-helper) (`agent-framework/`) | **Payload** | Agent prompts (`agents/*.md`), manifest, `build_team.py` orchestrator, 9 specialists, `chat.py` REPL |
| `azure-architecture-factory` (this repo) | **Factory** | BRD → diagram → Bicep + FastAPI wrapper + Dockerfile + tests + gates |

### How AAF generated this project

Driven by [`docs/brd-samples/brd-csa-helper-runtime.md`](../../docs/brd-samples/brd-csa-helper-runtime.md) through the `project-orchestrator` subagent. Each phase delegates to a specialist subagent:

| Phase | Subagent | Produced |
|---|---|---|
| 1 | `brd-to-architecture-diagram` | `diagrams/*.drawio` + `.md` |
| 2 | `source-code-maintainer` (python) | `src/api/main.py`, `Dockerfile`, `infra/**/*.bicep` |
| 2.5 | `contract-validator` (alignment) | BRD ↔ diagram ↔ code 3-way diff |
| 2.6 | `security-compliance-auditor` | secrets/MI/RBAC review |
| 2.7 / 2.8 | `source-code-maintainer` (audit modes) | error-handling + scalability gates |
| 3 | `bicep-infrastructure-validator` | `az bicep build` + lint |
| 3.7 | `source-code-maintainer` (test mode) | `tests/test_api.py`, pytest run |
| 4 | `production-environment-advisor` | `docs/production-checklist.md` |

Phase 1.5 (`agent-tooling-advisor`) was **skipped** because `BRD.implementation.agents = []` — this project hosts an existing runtime, it does not declare new Foundry agents.

### What AAF did NOT do

- It did **not** rewrite csa-helper agents — `build_team.py` and the 10 prompts in `agents/` are vendored verbatim via `git clone` in [`Dockerfile`](Dockerfile).
- It did **not** provision a new Azure OpenAI account — the existing `fbfoundrywestus` is referenced via [`infra/modules/rbac/aoai-role-assignment.bicep`](infra/modules/rbac/aoai-role-assignment.bicep) (cross-RG, role assignment only).
- It did **not** push or deploy — `deploy: false` and `factory: false` were set when invoking `project-orchestrator`.

### Decoupled iteration

```
edit agents in csa-helper       → rebuild image (acr build) → redeploy revision
edit infra/wrapper in this repo → az deployment group create → no agent changes
```
