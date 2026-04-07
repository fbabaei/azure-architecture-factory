# Azure Architecture Factory Quick Start

This repository supports three main workflows:

1. Run the end-to-end factory through `project-orchestrator`.
2. Use individual agents for architecture, implementation, validation, or deployment tasks.
3. Review the sample-project portfolio and validation evidence through the developer portal.

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
```

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
| `azure-architecture-implementer` | Convert diagram intent into code and Azure resources |
| `bicep-infrastructure-validator` | Validate and repair Bicep modules and params |
| `production-environment-advisor` | Produce runtime and deployment prerequisites |
| `azure-project-deployer` | Execute deployment for a prepared project |

## 3. Validate The Current Repository

Representative checks:

```powershell
python -m pytest .\projects\order-management-platform\tests\unit .\projects\order-management-platform\tests\integration -v --tb=short --no-header
python -m unittest discover .\projects\storage-self-service-provisioning\tests
```

These two suites are the current validation baseline surfaced by the demo portal because they exercise the strongest sample implementations in the repository.

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
