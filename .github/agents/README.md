# Custom Agents

## Agent Overview

```
project-orchestrator          ← START HERE — drives all agents end-to-end
│
├── project-state-manager         helper: project folders, logs, manifest state
├── brd-to-architecture-diagram   Phase 1: MCP Draw.io diagram from requirements
├── azure-architecture-implementer Phase 2: Python services + Bicep scaffolding
│   └── drawio-architecture-reader      helper: reads diagram, returns inventory
├── bicep-infrastructure-validator Phase 3: validate & self-heal Bicep files
├── production-environment-advisor Phase 4: production readiness checklist
├── azure-project-deployer        Phase 5: deploy to Azure (optional)
└── factory-handoff               Phase 6: promote project to factory portal (optional)

factory-handoff               ← standalone bridge to Azure Architecture Factory
│
├── reads  : projects/<slug>/docs/requirements.md
├── submits: POST /api/brd-intake on the factory portal
├── polls  : GET  /api/brd-runs/{runId} until completed
└── writes : factoryHandoff block into project-manifest.json
```

Each project the orchestrator creates is stored under `projects/<project-slug>/` with its own diagrams, source, infra, docs, and logs — fully isolated from other projects.

---

## Available Agents

### project-orchestrator ⭐ Recommended Entry Point
Use this agent to drive an entire project from requirements to production in one command.

Typical uses:
- Turn a BRD or PRD into a deployed Azure solution in one orchestrated flow.
- Generate architecture → scaffold code → validate infra → review production readiness → deploy.
- Create an isolated `projects/<name>/` folder containing everything: diagrams, code, infra, logs, docs.

Phase 1 is explicitly driven through the MCP Draw.io workflow via `brd-to-architecture-diagram`, not by manual diagram drafting.

Inputs accepted: `BRD.md`, `PRD.md`, or inline requirements text.

### azure-project-deployer
Use this agent to deploy a project's Bicep infrastructure to Azure.

Typical uses:
- Deploy a specific project's infra from `projects/<name>/infra/`.
- Run pre-deployment validation, create resource group, execute deployment, capture outputs.
- Update `DEPLOY.md` with actual resource names and endpoints after deployment.
- Called automatically by `project-orchestrator` at Phase 5.

Available standalone for re-deployments or environment promotions.

### project-state-manager
This is a helper subagent used by the orchestrator. It manages per-project folder structure, logs, and `project-manifest.json` state.

Typical uses:
- Initialize `projects/<name>/` structure for a new run.
- Record phase start/completion/failure in logs.
- Keep `project-manifest.json` valid and up to date.
- Make orchestrated projects restart-safe and independently auditable.

### azure-architecture-implementer
Use this agent to read a draw.io architecture diagram, map the design to Azure services, and scaffold a modular Python implementation with microservice boundaries.

Typical uses:
- Implement a diagram under `diagrams/`.
- Generate service structure and Azure mappings.
- Update supporting documentation after implementation.

### production-environment-advisor
Use this agent to inspect the repository and identify the production environment needed to run the project for real.

Typical uses:
- Find runtime and deployment prerequisites.
- Identify required Azure resources, identities, and secrets.
- Produce a production-readiness checklist.

### bicep-infrastructure-validator
Use this agent to validate and automatically fix Bicep infrastructure modules and parameters.

Typical uses:
- Audit all Bicep files for syntax, logic, and configuration errors.
- Validate parameter files against their related templates.
- Automatically detect and fix common issues (type mismatches, invalid properties, path issues, missing decorators).
- Generate validation reports with fixes applied.
- Self-heals infrastructure code without user intervention.

Required folder: `infra/` with Bicep modules and parameter files.

### brd-to-architecture-diagram
Use this agent to turn business or product requirements into a visual Azure architecture diagram using the MCP Draw.io server.

Typical uses:
- Generate an architecture diagram from `BRD.md` or `PRD.md`.
- Produce a `.drawio` file and companion notes in `diagrams/` from a written specification.
- Rapidly prototype infrastructure design from a business case.
- Validate that the right Azure services are chosen for stated requirements.

Requires: MCP Draw.io server running and accessible.

When called by `project-orchestrator`, this agent must follow the full MCP Draw.io sequence: `get-style-presets` → `search-shapes` → `create-groups` → `add-cells` → `add-cells-to-group` → `finish-diagram` → `export-diagram`.

### drawio-architecture-reader
This is a helper subagent used by the implementation agent. It reads diagrams and companion notes and returns an implementation inventory.

### factory-handoff
Use this agent to promote a locally scaffolded `project-orchestrator` project to the shared **Azure Architecture Factory** portal.

Typical uses:
- Submit a completed project's requirements to the factory BRD intake API.
- Poll the factory pipeline until it completes and retrieve the canonical project slug.
- Record the factory run ID and project URL back into the local `project-manifest.json`.
- Called optionally at the end of a `project-orchestrator` run when `factory: true` is specified.

Prerequisites: factory portal running (`python scripts/start_factory_portal.py`), `FACTORY_PORTAL_API_KEY` set if auth is enabled.

---

## Notes
- **Use `project-orchestrator` for new projects** — it calls all other agents in the correct order.
- Individual agents can still be invoked standalone for targeted tasks.
- Projects created by the orchestrator live under `projects/` with full isolation per project.
- Use `factory-handoff` after `project-orchestrator` to promote the project to the shared factory portal.
- The root `QUICKSTART.md` explains how to use the orchestrator and all individual agents.
