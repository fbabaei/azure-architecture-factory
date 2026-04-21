# Azure Architecture Factory Quick Start

This repository supports three main workflows:

1. Run the end-to-end factory through `project-orchestrator`.
2. Use individual agents for architecture, implementation, validation, or deployment tasks.
3. Review the sample-project portfolio and validation evidence through the developer portal.

The portal also ships two AI copilots — **💬 BRD Copilot** (bottom-left: draft or review BRDs against a 10-point readiness rubric) and **🛠️ Project Copilot** (tool-enabled, per-project: architecture Q&A, cost, observability, deploy commands). Both require Azure OpenAI env vars on the portal process. See [COPILOT_GUIDE.md](COPILOT_GUIDE.md) for the full capability reference.

## 1. Start With The Orchestrator

Use `project-orchestrator` when you want the repository to create an isolated project folder from requirements.

Before using the orchestrator on a new requirements document, classify it with [BRD_READINESS_GATE.md](BRD_READINESS_GATE.md).
Use [BRD_READINESS_SCORECARD.md](BRD_READINESS_SCORECARD.md) if you want a documented scored review.

Example prompt:

```text
Use the project-orchestrator agent.
Input: docs/BRD.md
Project name: customer-portal
Environment: dev
Region: eastus
Deploy: false
Runtime: auto
```

### The `Runtime` argument

`Runtime` controls which agent runtime the generated project ships. Pick one:

| Value | Ship | Use when |
| --- | --- | --- |
| `local` | Deterministic Python only | Pure ETL, reporting, infra automation. No LLM. |
| `agent-framework` | Both runtimes (SDK + local fallback) | Chat UX, document extraction, multi-turn clarification, Azure AI Foundry / Azure OpenAI. |
| `auto` *(default)* | Factory decides | You are not sure. The factory classifier in [`scripts/factory_runtime/`](../scripts/factory_runtime/) reads the BRD and picks one for you. |

The choice is recorded as `agent_runtime` in the project's `project-manifest.json`. The `agent-framework` option follows the pattern codified in [AGENT_FRAMEWORK_RUNTIME_PATTERN.md](AGENT_FRAMEWORK_RUNTIME_PATTERN.md): the SDK runtime is preferred when configured, the deterministic runtime is always the fallback, so the service stays online even without Foundry.

For the full decision flow — what signals the classifier looks for, where it runs, what the manifest looks like afterwards — see [BRD_CLASSIFICATION_FLOW.md](BRD_CLASSIFICATION_FLOW.md).

### Generation options (language, IaC tool, opt-outs)

Beyond `Runtime`, the BRD intake (portal or CLI) accepts these generation options — all optional with sensible defaults:

| Option | Values | Default | What it controls |
| --- | --- | --- | --- |
| `implementationLanguage` | `python`, `dotnet` | `python` (or inferred from BRD) | Which language agent emits the service scaffold. `dotnet` produces an ASP.NET Core 8 minimal API with xUnit tests and a multi-stage Dockerfile; `python` produces FastAPI + pytest. |
| `iacTool` | `bicep`, `terraform` | `bicep` (or inferred from BRD) | Which IaC agent generates `infra/`. Both paths produce equivalent resource shapes (Container Apps + managed identity + Key Vault + optional App Insights). |
| `networkTier` | `public`, `vnet-integrated`, `private` | `public` | See "Network Isolation Option" below. |
| `generateInfra` | `true`, `false` | `true` | Set to `false` to skip `infra/` generation for docs-only spikes. Phase 3 infra validation is skipped cleanly. |
| `runSecurityAudit` | `true`, `false` | `true` | Set to `false` to bypass the Phase 2.6 Security Gate (audit-only mode). |
| `enableObservability` | `true`, `false` | `true` | When on, scaffolds wire Application Insights via `APPLICATIONINSIGHTS_CONNECTION_STRING` (both Python and .NET paths). |

The factory also detects a workload **archetype** from the BRD — `extraction-chat` (document upload + clarification loop), `rag-qa` (corpus-grounded Q&A), or `api-service` (generic). The selected archetype drives the language agent's emission shape (e.g., extraction-chat produces 5 domain services and 6 endpoints instead of a single starter endpoint) and is recorded under `analysis.archetype` in `project-manifest.json`. See [docs/MDR_PY_VS_DOTNET.md](MDR_PY_VS_DOTNET.md) for a side-by-side of Python vs .NET output for the same `extraction-chat` BRD.

Expected output shape:

```text
projects/<project-name>/
├── docs/
├── diagrams/
├── src/
├── infra/
├── tests/
├── logs/
├── project-manifest.json
├── README.md
└── DEPLOY.md
```

## 2. Use Individual Agents

Use these when you only need one part of the workflow.

| Agent | Use Case |
| --- | --- |
| `brd-to-architecture-diagram` | Generate or import an Azure architecture diagram |
| `azure-architecture-implementer` | Convert diagram intent into Python services + Bicep scaffolding |
| `lang-dotnet-implementer` | Same as above but emits ASP.NET Core 8 services when `implementationLanguage` is `dotnet` |
| `bicep-infrastructure-validator` | Validate and repair Bicep modules and params |
| `terraform-infrastructure-validator` | Validate and repair Terraform configuration when `iacTool` is `terraform` |
| `production-environment-advisor` | Produce runtime and deployment prerequisites |
| `azure-project-deployer` | Execute deployment for a prepared project |

## 3. Validate The Current Repository

Representative checks:

```powershell
python -m pytest .\projects\order-management-platform\tests\unit .\projects\order-management-platform\tests\integration -v --tb=short --no-header
python -m unittest discover .\projects\storage-self-service-provisioning\tests
```

These two suites are the current validation baseline surfaced by the demo portal because they exercise the strongest sample implementations in the repository.

## 3a. What the portal classifier tells you

Every BRD submitted through the portal is scored by the factory classifier before the project is generated. The result appears on the project record as `suggestedRuntime` and inside `project-manifest.json` as `suggested_runtime`. It tells you whether the BRD looks LLM-driven (signals like *chat agent*, *RAG*, *document extraction*, *Azure AI Foundry*) or whether deterministic Python is enough. You do not need to install the preview Agent Framework SDK for this to work — the deterministic classifier is always active inside the portal container.

To opt the portal classifier into its SDK path, set on the Container App:

- `FACTORY_AGENT_FRAMEWORK_ENABLED=1`
- `FOUNDRY_PROJECT_ENDPOINT=https://<project>.services.ai.azure.com/api/projects/<name>`
- `FOUNDRY_MODEL_DEPLOYMENT_NAME=<deployment>`

If any of those are missing, or if the preview SDK is not installed, the portal silently falls back to the deterministic classifier. See [`scripts/factory_runtime/README.md`](../scripts/factory_runtime/README.md).

## 4. Launch The Developer Portal

```powershell
pip install -r .\demo\requirements.txt
.\scripts\start_portal_from_anywhere.ps1
```

Portal endpoints:

- `http://localhost:5000/` main demo
- `http://localhost:5000/factory-readiness` readiness dashboard
- `http://localhost:5000/brd-readiness` BRD readiness dashboard
- `http://localhost:5000/order-monitoring-dashboard` order-management monitoring view
- `http://localhost:5000/presentation` leadership brief

When submitting a BRD from the portal intake form, set **Network Isolation**:

- `Public` for internet-facing baseline generation
- `VNet-integrated` to include starter VNet + NSG + delegated app subnet resources
- `Private` to include starter VNet + NSG + private endpoint subnet resources

## 5. Use The Sample Portfolio

Current sample outputs under `projects/` are intentionally mixed:

- `order-management-platform`: strongest full-lifecycle evidence
- `storage-self-service-provisioning`: service-oriented implementation with runnable tests
- `aks-microservices-demo`: infrastructure and platform-oriented output
- `ecommerce-demo`: lightweight web sample
- `fabric-medallion-pipeline`: restored data-pipeline sample with medallion stages, governance helpers, and runnable tests

Use them as evidence of what the factory can already produce and where it still needs more standardization.

## 5a. Gate New BRDs First

Use [BRD_READINESS_GATE.md](BRD_READINESS_GATE.md) to classify incoming requirements as:

- `Auto-Ready`
- `Auto-Ready With Guardrails`
- `Architect Review Required`

This repository is strong for many Azure-first BRDs, but this gate should be used before treating it as universally ready for any requirements document.

## 6. Repo Layout

- `.github/` custom Copilot instructions and agent definitions
- `diagrams/` reusable Azure architecture source artifacts
- `projects/` generated and sample project outputs
- `infra/` shared Bicep modules and parameter files
- `demo/` developer-facing portal and dashboards
- `docs/` repository guidance and positioning

If you are new to Draw.io files, see [VIEW_DETAILED_ARCHITECTURE.md](VIEW_DETAILED_ARCHITECTURE.md).
