# Azure Architecture Factory

Azure Architecture Factory is an internal Azure delivery workspace built around custom Copilot agents. Its purpose is to reduce the gap between requirements and working project structure by standardizing how architecture, code, infrastructure, documentation, and readiness evidence are produced.

## What The Repository Contains

- Agent definitions under [../.github/agents/README.md](../.github/agents/README.md)
- Reusable architecture diagrams under [../diagrams](../diagrams)
- Shared Bicep modules under [../infra/README.md](../infra/README.md)
- Reusable project templates under [../factory-templates/agent-framework/README.md](../factory-templates/agent-framework/README.md)
- Sample project outputs under [../projects](../projects)
- A developer-facing portal under [../demo](../demo)

## Factory Conventions

- [AGENT_FRAMEWORK_RUNTIME_PATTERN.md](AGENT_FRAMEWORK_RUNTIME_PATTERN.md) — how generated projects adopt the Microsoft Agent Framework SDK runtime alongside a deterministic fallback

## Delivery Model

The intended workflow is:

1. Start from a BRD, PRD, or structured prompt.
2. Generate or import an Azure architecture diagram.
3. Scaffold service code, tests, and project documentation.
4. Produce and validate Bicep infrastructure.
5. Review production readiness.
6. Optionally deploy to Azure.

The repository demonstrates that workflow through multiple sample outputs rather than a single showcase.

## Agent Roles

| Agent | Role |
| --- | --- |
| `project-orchestrator` | Drives the end-to-end lifecycle from requirements to finished project folder |
| `brd-to-architecture-diagram` | Produces Azure diagrams and companion notes |
| `azure-architecture-implementer` | Converts diagram intent into source code and Azure mappings |
| `bicep-infrastructure-validator` | Validates and repairs Bicep modules and parameter files |
| `production-environment-advisor` | Produces production-readiness prerequisites and blockers |
| `azure-project-deployer` | Handles optional deployment execution |

## Repository Evidence

The repo now presents a portfolio of sample outputs in [../projects](../projects):

- `order-management-platform` is the strongest full-lifecycle example with diagrams, source code, tests, infrastructure, production checklist, and deployment guide.
- `storage-self-service-provisioning` demonstrates a service-oriented implementation with runnable tests and operational flow.
- `aks-microservices-demo` shows platform and infrastructure-oriented output for AKS workloads.
- `ecommerce-demo` provides a lightweight web-facing example.
- `fabric-medallion-pipeline` restores the original data-pipeline sample with Bronze, Silver, and Gold stages, governance helpers, analytics outputs, and Bicep infrastructure.

This mix is useful because it shows where the factory already produces production-style outputs and where some sample types are still lighter-weight.

## Local Validation Paths

Use these representative checks when validating the repository locally:

```powershell
cd ..
python -m pytest .\projects\order-management-platform\tests\unit .\projects\order-management-platform\tests\integration -v --tb=short --no-header
python -m unittest discover .\projects\storage-self-service-provisioning\tests
```

To launch the developer portal:

```powershell
cd ..\demo
pip install -r requirements.txt
python app.py
```

## Recommended Reading Order

1. [QUICKSTART.md](QUICKSTART.md)
2. [PRD.md](PRD.md)
3. [BRD.md](BRD.md)
4. [BRD_READINESS_GATE.md](BRD_READINESS_GATE.md)
5. [BRD_READINESS_SCORECARD.md](BRD_READINESS_SCORECARD.md)
6. [../demo/README.md](../demo/README.md)

## Current Positioning

This repository is best described as an internal architecture-delivery factory with reusable agent workflows and a portfolio of sample outputs. The Fabric Medallion sample is available again as one reference implementation, but it is no longer the sole centerpiece of the repository.

Use [BRD_READINESS_GATE.md](BRD_READINESS_GATE.md) before assuming an incoming BRD is suitable for fully automated execution.
