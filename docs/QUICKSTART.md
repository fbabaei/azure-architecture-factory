# Azure Architecture Factory — Quick Start

This repository is an **AI-driven architecture-to-implementation platform** with three primary entry points:
- **Full project lifecycle** with the `project-orchestrator` agent (recommended)
- **Individual agents** for targeted tasks (architecture, infra validation, deployment)
- **Reference pipeline** under `fabric_medallion/` (working Fabric Medallion implementation)

## 1. Read the Core Docs
- Start with `README.md` for repo orientation.
- Use `PRD.md` for product and technical requirements.
- Use `BRD.md` for business context and expected outcomes.
- Use `diagrams/` for the source architecture artifacts.
- Use `projects/` for isolated project outputs created by the orchestrator.

## 2. Recommended: Full Lifecycle with the Orchestrator

The `project-orchestrator` agent drives everything in one command — from requirements to production.

Phase 1 is not a freeform diagram step. The orchestrator requires the Draw.io MCP sequence so the architecture is created through the server workflow and exported as a real `.drawio` artifact.

### What It Does
```
Requirements (BRD/PRD/prompt)
    │
    ▼
[Phase 0] project-state-manager        → projects/<name>/ + logs + manifest
    │
    ▼
[Phase 1] brd-to-architecture-diagram   → MCP Draw.io workflow → projects/<name>/diagrams/*.drawio
    │
    ▼
[Phase 2] azure-architecture-implementer → projects/<name>/src/ + infra/
    │
    ▼
[Phase 3] bicep-infrastructure-validator → auto-fix infra errors
    │
    ▼
[Phase 4] production-environment-advisor → projects/<name>/docs/production-checklist.md
    │
    ▼
[Phase 5] azure-project-deployer         → deploy to Azure (if requested)
    │
    ▼
[Phase 6] Generate README.md, DEPLOY.md, project-manifest.json
```

### From a Requirements File

```text
Use the project-orchestrator agent.
Input: BRD.md
Project name: fabric-medallion-v2
Environment: dev
Region: eastus
Deploy: false
```

### From an Inline Prompt

```text
Use the project-orchestrator agent.
Requirements: Build a real-time IoT telemetry platform that ingests sensor data,
enriches it with ML predictions, stores results in a time-series database,
and serves dashboards to operations teams.
Project name: iot-telemetry-platform
Environment: dev
Region: westeurope
Deploy: false
```

### With Full Deployment

```text
Use the project-orchestrator agent.
Input: PRD.md
Project name: customer-portal
Environment: prod
Region: eastus2
Deploy: true
```

### Project Output Structure
Every project gets an isolated `projects/<name>/` folder:
```
projects/<name>/
├── docs/           ← requirements, architecture decisions, production checklist
├── diagrams/       ← .drawio diagram + architecture notes
├── src/            ← Python microservices
├── infra/          ← Bicep modules + environment parameters
├── tests/          ← unit and integration tests
├── logs/           ← orchestration.log + per-phase logs
├── project-manifest.json
├── README.md
└── DEPLOY.md
```

`project-state-manager` is the helper agent that initializes this structure and keeps logs plus `project-manifest.json` synchronized across all phases.

---

## 3. Use Individual Agents
The custom agents live under `.github/agents/`. Use these for targeted tasks.

### Agent: `azure-architecture-implementer`
Use this when you want Copilot to turn a diagram into an Azure-backed implementation.

Suggested prompt:

```text
Use the azure-architecture-implementer agent on diagrams/azure-ai-foundry-architecture.drawio.
Map the diagram to Azure resources, scaffold modular Python services, and update docs for the implementation.
```

What it does:
- reads the diagram and companion notes
- maps components to Azure resources
- scaffolds modular Python services with microservice boundaries
- updates supporting docs when implementation changes

### Agent: `production-environment-advisor`
Use this when you want Copilot to identify the real production environment required to run the project.

Suggested prompt:

```text
Use the production-environment-advisor agent on the repository.
List the runtime, Azure, identity, networking, secret, monitoring, and deployment prerequisites for production.
```

What it does:
- inspects dependency manifests and env templates
- lists required Azure resources and identities
- identifies production gaps and readiness blockers

### Agent: `bicep-infrastructure-validator`
Use this when you want Copilot to audit and auto-fix all Bicep infrastructure modules and parameters.

Suggested prompt:

```text
Use the bicep-infrastructure-validator agent.
Scan all Bicep files in infra/, check for errors, and auto-fix them. Return a validation report.
```

What it does:
- validates all `.bicep` and `.bicepparam` files for syntax and logic errors
- automatically fixes common issues (type mismatches, invalid properties, path issues, missing decorators)
- re-validates after fixes to confirm resolution
- generates a structured report of issues found and fixed
- runs without user intervention (self-healing)

### Agent: `brd-to-architecture-diagram`
Use this when you want to generate a diagram from requirements without the full orchestration flow.

Suggested prompt:

```text
Use the brd-to-architecture-diagram agent on BRD.md.
Analyze the business requirements, map them to Azure services, and generate an architecture diagram.
Save the result to diagrams/.
```

What it does:
- parses `BRD.md`, `PRD.md`, or inline requirements text
- maps each requirement to the appropriate Azure service
- uses the MCP Draw.io server (`mcp_draw_io_mcp_*` tools) to build the diagram
- saves the `.drawio` file and companion notes to `diagrams/`

Requires: MCP Draw.io server running and accessible in VS Code.

### Agent: `azure-project-deployer`
Use this when you want to deploy a project's infrastructure to Azure (standalone, or called by the orchestrator).

Suggested prompt:

```text
Use the azure-project-deployer agent.
Project path: projects/my-project
Environment: dev
Region: eastus
Subscription: <subscription-id>
```

What it does:
- validates Bicep deployment with `az deployment group validate` before executing
- creates the Azure resource group if it does not exist
- runs `az deployment group create` with the appropriate parameter file
- captures all outputs (FQDNs, endpoints, connection strings)
- writes a full deployment log to `projects/<name>/logs/phase-5-deployment.log`
- updates `projects/<name>/DEPLOY.md` with actual deployed resource names

### Helper Agent: `project-state-manager`
This helper is called by `project-orchestrator` to keep each project isolated and well-tracked.

What it does:
- creates and verifies the standard `projects/<name>/` folder structure
- initializes and updates `project-manifest.json`
- writes `logs/orchestration.log` and per-phase logs
- records statuses, artifacts, timestamps, and failures in a machine-readable way

## 4. Run the Reference Pipeline (Fabric Medallion)

### Install dependencies

```powershell
cd .\fabric_medallion
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Run in sample mode

```powershell
python .\run_pipeline.py --mode sample
```

### Run tests

```powershell
python -m unittest discover .\tests
```

## 5. Prepare for Real Azure Execution
1. Copy `.\fabric_medallion\.env.example` to `.\fabric_medallion\.env`.
2. Fill in ADLS, Snowflake, Power BI, retry, and token settings.
3. Prefer managed identity and Key Vault for production deployments.
4. Use the `production-environment-advisor` agent before going live.

## 6. Recommended Working Order

**For new projects:** Use `project-orchestrator` — it handles all steps automatically.

**For existing projects or targeted tasks:**
1. Pick the target architecture diagram from `diagrams/`.
2. Run `azure-architecture-implementer` to generate or refine the implementation.
3. Review `README.md`, `PRD.md`, `BRD.md`, and service docs for consistency.
4. Run the pipeline locally in sample mode.
5. Run `production-environment-advisor` to identify production prerequisites.
6. Run `bicep-infrastructure-validator` to validate and fix all Bicep files.
7. Run `azure-project-deployer` to deploy infrastructure to Azure.

## 7. Repository Layout
- `.github/`: Copilot instructions and custom agents
- `diagrams/`: shared architecture source of truth (Draw.io files)
- `projects/`: isolated project outputs — one subfolder per project created by the orchestrator
- `fabric_medallion/`: current Python medallion implementation
- `infra/`: Bicep infrastructure for Azure AI Foundry architecture (modular, multi-environment)
- `PRD.md`: product requirements
- `BRD.md`: business requirements
- `USE_CASES_AND_PROBLEMS_SOLVED.md`: scenario-driven context

## 8. Deploy Bicep Infrastructure (Quick Start)

The AI Foundry architecture is scaffolded with production-ready Bicep:

```bash
# Set up resource group
az group create --name ai-agent-dev-rg --location eastus

# Customize deployment (optional)
code infra/params/dev.bicepparam  # Edit container image, SKUs, etc.

# Deploy
az deployment group create \
  --name ai-agent-dev \
  --resource-group ai-agent-dev-rg \
  --template-file infra/main.bicep \
  --parameters infra/params/dev.bicepparam

# Retrieve outputs (container app URL, Key Vault, Cosmos DB endpoint, etc.)
az deployment group show \
  --name ai-agent-dev \
  --resource-group ai-agent-dev-rg \
  --query 'properties.outputs' -o json
```

For detailed guidance, see [infra/DEPLOY.md](infra/DEPLOY.md).
