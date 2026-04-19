# Custom Agents

## Agent Overview

```
modernization-to-factory      ← START HERE for legacy app modernization
│
├── [Phase 1] assess legacy codebase (technology, architecture, risk)
├── [Phase 2] map components to Azure target services
├── [Phase 3] write modernization-assessment.md
├── [Phase 4] generate target-state BRD → requirements.md
└── [Phase 5] → project-orchestrator (full factory pipeline)

project-orchestrator          ← START HERE for greenfield / BRD-first delivery
│
├── project-state-manager         helper: project folders, logs, manifest state
├── brd-to-architecture-diagram   Phase 1: MCP Draw.io diagram from requirements
├── azure-architecture-implementer Phase 2: Python services + Bicep scaffolding
│   └── drawio-architecture-reader      helper: reads diagram, returns inventory
├── bicep-infrastructure-validator Phase 3: validate & self-heal Bicep files
├── production-environment-advisor Phase 4: production readiness checklist
├── azure-project-deployer        Phase 5: deploy to Azure (optional)
├── project-observability-advisor Phase 6: audit and report on observability (optional)
├── project-traceability-advisor  Phase 6b: requirement → code → test → infra coverage (optional)
└── factory-handoff               Phase 7: promote project to factory portal (optional)

factory-workflow-guide        ← USE ANY TIME you are stuck, unsure, or something looks wrong
│
├── reads  : project-manifest.json, logs/, folder structure on disk
├── detects: missing steps, failed phases, misconfigured artifacts, wrong sequences
├── reports: 🔴 Critical / 🟠 Warning / 🟡 Advisory findings with exact fixes
└── outputs: clear "next step" instruction + which agent to run next

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

### factory-workflow-guide 🧭 Use When Stuck or Unsure
Use this agent any time you are confused, stuck, or want to verify your project is on track.

Typical uses:
- "I just ran the orchestrator — did it work? What should I do next?"
- "Something looks wrong with my project — what is it and how do I fix it?"
- "I'm new to the factory — walk me through what I need before I start."
- Check project manifest, logs, and on-disk structure for missing or failed phases.
- Surface 🔴 Critical / 🟠 Warning / 🟡 Advisory issues with exact fix instructions.
- Recommend the precise next agent to run, with the exact argument to pass.

Can be run proactively after every phase as a health check, or reactively when something seems wrong. Available from any project card via the **🧭 Guide Me** link.

---

### project-orchestrator ⭐ Recommended Entry Point
Use this agent to drive an entire project from requirements to production in one command.

Typical uses:
- Turn a BRD or PRD into a deployed Azure solution in one orchestrated flow.
- Generate architecture → scaffold code → validate infra → review production readiness → deploy.
- Create an isolated `projects/<name>/` folder containing everything: diagrams, code, infra, logs, docs.

Phase 1 is explicitly driven through the MCP Draw.io workflow via `brd-to-architecture-diagram`, not by manual diagram drafting.

Inputs accepted: `BRD.md`, `PRD.md`, or inline requirements text.

**Update Mode — BRD changes on existing projects**

The orchestrator also runs in Update Mode when a BRD is resubmitted for a project that already exists. Triggers:
- Portal resubmission (writes `projects/<slug>/.brd-update-pending.json`).
- Explicit CLI / GHCP invocation with `update: true` and `slug: <existing-slug>`.
- Drift detection: `docs/requirements.md` is newer than the manifest's Phase 1 completion time.

In Update Mode the orchestrator:
1. Snapshots the prior BRD, diagram, and notes under `projects/<slug>/docs/history/` and `projects/<slug>/diagrams/history/`.
2. Computes a BRD diff and writes it to `docs/brd-diff-v<N>.md`.
3. Calls `drawio-architecture-reader` to inventory the current architecture.
4. Calls `brd-to-architecture-diagram` with the diff + inventory so the new diagram preserves unchanged components and only applies deltas.
5. Calls `azure-architecture-implementer` in incremental mode — added services are scaffolded, removed services are moved to `src/_removed/v<N>/`, and modified services are updated in place.
6. Re-runs Bicep validation and refreshes the production checklist. Never auto-deploys an update.

### azure-project-deployer
Use this agent to deploy a project's Bicep infrastructure to Azure.

Typical uses:
- Deploy a specific project's infra from `projects/<name>/infra/`.
- Run pre-deployment validation, create resource group, execute deployment, capture outputs.
- Update `DEPLOY.md` with actual resource names and endpoints after deployment.
- Called automatically by `project-orchestrator` at Phase 5.

Available standalone for re-deployments or environment promotions.

### project-traceability-advisor
Use this agent to produce a full requirements traceability report for any factory-generated project.

Typical uses:
- Extract and normalize all BRD requirements, assign stable `REQ-NNN` IDs.
- Map each requirement to the source files, Bicep modules, and test cases that implement it.
- Compute coverage metrics: % Implemented / Partial / Gap; test coverage %; infrastructure coverage %.
- Identify priority gaps: security requirements with no Bicep resource, functional requirements with no code, untested implementations.
- Save a dated traceability report to `projects/<name>/docs/traceability-report-<date>.md`.
- Optionally update `project-manifest.json` with a structured `traceability` block.

Can be run immediately after orchestrator generation or at any point during refinement to measure progress.

### project-observability-advisor
Use this agent to audit, configure, and report on observability and monitoring for a deployed project.

Typical uses:
- Audit the four observability pillars (Metrics, Logs, Traces, Alerts) for a deployed Azure project.
- Identify gaps: missing Application Insights wiring, absent alert rules, orphaned Log Analytics workspaces.
- Generate ready-to-run KQL queries for exceptions, 5xx spikes, slow dependencies, and container restarts.
- Optionally produce Bicep modules to provision missing alert rules, action groups, and App Insights components.
- Save a dated observability report to `projects/<name>/docs/observability-report-<date>.md`.

Can be invoked before deployment (static Bicep audit) or after (live Azure query + gap assessment).

### project-cost-analyzer
Use this agent to analyze actual and projected Azure costs for a generated project.

Typical uses:
- Query Azure Cost Management for actual post-deployment spend by service and resource.
- Scan Bicep files to build a pre-deployment estimate for comparison.
- Identify top cost drivers and optimization opportunities (scale-to-zero, SKU right-sizing, tier changes).
- Save a dated cost report to `projects/<name>/docs/cost-report-<date>.md`.

Can be launched directly from the portal's Cost Tools modal via the **▷ Analyze Costs with GitHub Copilot** button.

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

### modernization-to-factory ⭐ Entry Point for Legacy Modernization
Use this agent when you have an existing application that needs to be re-platformed or re-architected onto Azure.

Typical uses:
- Assess a monolithic Java, .NET, Python, or Node.js application and generate an Azure target baseline.
- Detect technology stack, architecture patterns, and modernization debt automatically.
- Produce a structured Assessment + BRD describing the Azure target state.
- Hand off to `project-orchestrator` to generate architecture diagrams, code scaffolding, and Bicep infra.

Inputs accepted: path to legacy codebase, optional technology hint (java/dotnet/python/lambda), optional target constraints.

Outputs written before factory handoff:
- `projects/<slug>/docs/modernization-assessment.md` — full assessment evidence
- `projects/<slug>/docs/requirements.md` — generated target-state BRD

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
- **Use `modernization-to-factory` for legacy apps** — it assesses the codebase, writes the BRD, then calls `project-orchestrator` automatically.
- **Use `project-orchestrator` for new projects** — it calls all other agents in the correct order.
- Individual agents can still be invoked standalone for targeted tasks.
- Projects created by the orchestrator live under `projects/` with full isolation per project.
- Use `factory-handoff` after `project-orchestrator` to promote the project to the shared factory portal.
- The root `QUICKSTART.md` explains how to use the orchestrator and all individual agents.
