# Custom Agents

> **Scoping model:** AAF's 20 agents are organized into three conceptual layers — **Intake → Design → Architecture** — with a separate **validation layer** (`contract-validator`) and **orchestration control plane** (`project-orchestrator`). See [`docs/AAF_AGENT_SCOPING.md`](../../docs/AAF_AGENT_SCOPING.md) for the diagram, layer responsibilities, and inter-agent contract schemas under [`factory-templates/contracts/`](../../factory-templates/contracts/).

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
│                                 (+ Phase 2.5 modes: extract-inventory, update)
├── azure-architecture-implementer Phase 2: Python services + Bicep scaffolding
│   │                             (+ Phase 2.5/3.7 modes: incremental, generate-tests, fix-tests)
│   │                             OWNS: new services, new Bicep modules, tests, initial docs
│   └── drawio-architecture-reader      helper: reads diagram, returns inventory
├── knowledge-retrieval-architect Phase 2 (conditional): designs + scaffolds the RAG/search pipeline
│                                 (modes: design, scaffold, audit) — runs only when retrieval is required
│                                 OWNS: data source + index + skillset + indexer, chunking, embeddings,
│                                       semantic reranker + min_reranker_score, agentic retrieval
│                                       (+ Phase 2.5 mode: inventory → canonical JSON)
├── source-code-maintainer        Phase 2 follow-up + Phase 2.5/2.6/2.7/2.8/3.7 loops (Python)
│                                 (modes: drift-check, inventory, error-handling-audit, scalability-audit, add-to-service, refactor, sync)
│                                 OWNS: changes INSIDE existing services — never creates a new service
├── lang-dotnet-implementer       Phase 2 + follow-up loops when BRD.implementation.language resolves to "dotnet" (includes "csharp" alias)
│                                 (modes: scaffold, sync, add-to-service, refactor, drift-check)
│                                 OWNS: ASP.NET Core 8 services under src/, xUnit tests, .NET Dockerfiles
├── [Phase 2.5] Alignment Convergence Loop — BRD↔diagram↔code 3-way diff (≥3 iterations)
├── security-compliance-auditor   Phase 2.6: read-only security + compliance audit
│                                 OWNS: secrets, identity, authZ, CVEs, HIPAA/SOC2/PCI/GDPR
├── [Phase 2.6] Security & Compliance Gate — audit + fix until 0 critical / 0 major (≤3 iterations)
├── [Phase 2.7] Error-Handling Gate — audit + fix until 0 critical / 0 major (≤3 iterations)
├── [Phase 2.8] Scalability Gate — code + infra audit until 0 critical / 0 major (≤3 iterations)
├── bicep-infrastructure-validator Phase 3: validate & self-heal Bicep files
│                                 (+ Phase 2.6/2.8 modes: security + scalability infra fixes)
│                                 OWNS: Bicep syntax, module wiring, infra-layer security + scalability fixes
├── [Phase 3.7] Test Convergence Loop — generate + run tests until green (≥3 iterations)
├── production-environment-advisor Phase 4: production readiness checklist (READ-ONLY)
├── aca-express-deployer          Phase 5 (Path A): deploy HTTP workloads via ACA Express (preview)
│                                 NO Bicep, NO environment wait — sub-minute deploy
│                                 Eligible: HTTP-only, no GPU/VNet/Dapr/jobs, westcentralus or eastasia
│                                 Falls back to azure-project-deployer when not eligible
├── azure-project-deployer        Phase 5 (Path B): standard Bicep-based Azure deploy (fallback / non-Express)
├── repo-change-agent             Existing-repo enhancement workflow (portal repo intake)
│                                 OWNS: repo-local analysis, change decisions, implementation, validation, change summary
│                                 DOES NOT OWN: clone/branch/push/PR side effects
├── project-observability-advisor Phase 6: audit and report on observability (optional)
├── project-traceability-advisor  Phase 6b: requirement → code → test → infra coverage (optional)
└── factory-handoff               Phase 7: promote project to factory portal (optional)
│                                 OWNS: repo-local analysis, change decisions, implementation, validation, change summary
│                                 DOES NOT OWN: clone/branch/push/PR side effects
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

contract-validator            ← validation layer (separated from generation)
│
├── reads  : projects/<slug>/docs/contracts/{intake,design,architecture}.json
├── checks : factory-templates/contracts/*.schema.json + cross-references
├── writes : projects/<slug>/docs/contracts/<phase>-validation.json
└── verdict: pass | fail with next_action: block | proceed | proceed_with_warnings

agent-tooling-advisor         ← Foundry tool + prompt recommender (Phase 1.5)
│
├── reads  : BRD.implementation.agents[], diagram data flows
├── infers : recommended_capabilities (file_search / code_interpreter / function_calling)
├── splits : file_search (Foundry-managed) vs azure_ai_search (BYO enterprise index)
├── drafts : function tool signatures + baseline system prompt per agent
└── writes : projects/<slug>/docs/agents/agent-tooling.{json,md}
                (hands off to knowledge-retrieval-architect when azure_ai_search is recommended)

knowledge-retrieval-architect ← retrieval (RAG) pipeline designer (Phase 2, conditional)
│
├── reads  : BRD, diagram, agent-tooling.json
├── decides: file_search vs azure_ai_search (deterministic rule)
├── designs: data source + index schema + skillset + indexer, chunking, embeddings,
│            semantic reranker + min_reranker_score, index projections, knowledge store,
│            optional agentic retrieval, MI-first role assignments
└── writes : projects/<slug>/docs/retrieval/retrieval-design.{json,md} (+ scaffolded code/infra)
```

Each project the orchestrator creates is stored under `projects/<project-slug>/` with its own diagrams, source, infra, docs, and logs — fully isolated from other projects.

---

## Alignment & Test Convergence (Mandatory)

Every project generated by `project-orchestrator` — greenfield or BRD update — runs **five** non-optional gates:

- **Phase 2.5 — Alignment Convergence Loop** (minimum 3 iterations, max 5): a 3-way diff across BRD, diagram, and code/infra driven by `brd-to-architecture-diagram` (extract-inventory), `drawio-architecture-reader` (inventory), and `source-code-maintainer` (inventory). Gaps are closed by `azure-architecture-implementer` (incremental) and `brd-to-architecture-diagram` (update). Orphaned code is flagged for human review, never auto-deleted.
- **Phase 2.6 — Security & Compliance Gate** (max 3 iterations): `security-compliance-auditor` scans code, infra, dependencies, and BRD-declared frameworks (HIPAA, SOC 2, PCI, GDPR). Every finding carries a `fixer` field so the orchestrator routes fixes deterministically to `source-code-maintainer refactor`, `bicep-infrastructure-validator`, or `azure-architecture-implementer incremental`. `human_review` findings always escalate.
- **Phase 2.7 — Error-Handling Gate** (max 3 iterations): `source-code-maintainer error-handling-audit` + `refactor`, with `azure-architecture-implementer incremental` for missing modules. The authoritative contract lives in `azure-architecture-implementer.agent.md → Error Handling Standards`.
- **Phase 2.8 — Scalability Gate** (max 3 iterations): `source-code-maintainer scalability-audit` against both `src/` and `infra/`; code-layer fixes go to `source-code-maintainer refactor`, infra-layer fixes go to `bicep-infrastructure-validator scalability-review`, missing artifacts to `azure-architecture-implementer incremental`. Cost-impact notes surface in the final report. The authoritative contract lives in `azure-architecture-implementer.agent.md → Scalability Standards`.
- **Phase 3.7 — Test Convergence Loop** (minimum 3 iterations, max 5): tests are generated by `azure-architecture-implementer generate-tests` from Phase 2.5's test-impact handoff, run with pytest, and fixes are delegated per failure classification (code defect → `source-code-maintainer refactor`, infra defect → `bicep-infrastructure-validator`, test defect → `azure-architecture-implementer fix-tests`).

Outputs land under `projects/<slug>/docs/alignment/`, `projects/<slug>/docs/security/`, `projects/<slug>/docs/error-handling/`, `projects/<slug>/docs/scalability/`, and `projects/<slug>/docs/test-convergence/`. The gates are recorded in `project-manifest.json` under `phases.2_5_alignment_convergence`, `phases.2_6_security_gate`, `phases.2_7_error_handling_gate`, `phases.2_8_scalability_gate`, and `phases.3_7_test_convergence`.

## Role Boundaries (Owns vs. Does Not Own)

To eliminate overlap between agents that both touch code or infra:

| Agent | Owns | Explicitly does NOT own |
|-------|------|------------------------|
| `azure-architecture-implementer` | First-time scaffolding of a new service, new Bicep modules from the diagram, test generation, NFR materialization, initial docs. | Modifying files inside an already-scaffolded service (→ maintainer); security audits (→ auditor); Bicep syntax fixes (→ validator). |
| `source-code-maintainer` | Incremental changes inside existing services, drift detection, code + infra inventory, error-handling + scalability audits, refactors driven by any gate, retiring removed components. | Creating a brand-new service (→ implementer); Bicep syntax fixes (→ validator); security audits (→ auditor). |
| `bicep-infrastructure-validator` | Bicep / `.bicepparam` syntax validation + auto-fix, module wiring, infra-layer scalability + security fixes dispatched by the gates. | Creating new Bicep modules (→ implementer); deploying infra (→ deployer); source-code edits (→ maintainer). |
| `security-compliance-auditor` | Security + compliance audit only (READ-ONLY). | Applying any fix; runtime advisory (→ production-environment-advisor). |
| `production-environment-advisor` | READ-ONLY pre-deploy prerequisites checklist. | Applying fixes of any kind (→ the gates); post-deploy analysis (→ advisor agents). |
| `repo-change-agent` | Existing-repo analysis, architecture-aligned change selection, implementation, local validation, `AAF-change-summary.md`. | Clone/branch/commit/push/PR operations (→ portal backend / repo ops layer); greenfield factory generation (→ orchestrator). |

| `contract-validator` | Schema-validating inter-agent handoffs (intake / design / architecture contracts) and emitting a block/proceed verdict. READ-ONLY. | Generating or repairing contract instances (→ the producing agent in the layer above); fixing code, infra, or diagrams. |
| `agent-tooling-advisor` | Recommending Foundry capabilities + tools + a baseline system prompt for each `BRD.implementation.agents[]` entry; distinguishing `file_search` from `azure_ai_search`. READ-ONLY. | Materializing tools into source code (→ language specialist); designing the retrieval pipeline (→ knowledge-retrieval-architect); modifying the BRD; runtime prompt optimization (→ Foundry `prompt_optimize`). |
| `knowledge-retrieval-architect` | Designing + scaffolding the retrieval (RAG) subsystem when required: `file_search` vs `azure_ai_search` choice, data source + index + skillset + indexer, chunking, embedding model + dimensions, semantic reranker + `min_reranker_score`, index projections, knowledge store, optional agentic retrieval, and the MI-first role assignments it declares. | Creating the owning microservice (→ implementer); editing already-scaffolded service code (→ maintainer); Bicep syntax validation (→ validator); applying data-plane RBAC (→ deployment phase); security audit (→ auditor). |

Full protocol and troubleshooting: [`../../docs/ALIGNMENT_CONVERGENCE_GUIDE.md`](../../docs/ALIGNMENT_CONVERGENCE_GUIDE.md).

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

**Chat wake-up from GHCP**

The orchestrator also accepts chat-driven wake-up calls from GitHub Copilot Chat. Start a message with `wakeup`, `wake up`, `hey orchestrator`, `hey factory`, or `hey project` and provide the target slug plus either a file path, an attached file, or a pasted change block. Wake-up calls route through Update Mode — they cannot create new projects. Example:

```
wakeup project: customer-analytics-platform changes: ./inbox/new-fraud-requirement.md
```

```
Hey factory — slug: eldercare-facility
paste:
- Add HIPAA audit log export every 24h
- Remove legacy SMS notifier
```

Supports `dry-run: true` for plan-only output and `mode: drift-check | sync | generate | refactor` to override the default update flow.

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

### knowledge-retrieval-architect
Use this agent in Phase 2 — **only when the project needs retrieval** (a knowledge base, grounded answers, document/semantic search, or an `azure_ai_search` tool recommended by `agent-tooling-advisor`). It designs and scaffolds the retrieval (RAG) subsystem that `azure-architecture-implementer` cannot build on its own.

Typical uses:
- Decide `file_search` (Foundry-managed) vs `azure_ai_search` (bring-your-own enterprise index).
- Design the Azure AI Search pull pipeline: data source + index schema + skillset + indexer.
- Set chunking (size/overlap), embedding model + dimensions, semantic reranking + `min_reranker_score`, index projections, knowledge store, and the optional agentic-retrieval (knowledge base) path.
- Emit a retrieval design contract (`docs/retrieval/retrieval-design.json`) plus scaffolded ingestion + query code and Search Bicep with MI-first role assignments.

It skips cleanly when no retrieval signal is present, and hands its query module to the language specialist for service wiring.

### source-code-maintainer
Use this agent to keep a project's source code in sync with its architecture over time. Complements `azure-architecture-implementer` — the implementer scaffolds, the maintainer maintains.

Typical uses:
- Drift check: compare the `.drawio` component inventory against what exists under `src/`.
- Sync mode: during BRD updates, add code for new components, retire code for removed components (moved to `src/_removed/v<N>/`, never deleted), refactor modified components in place.
- Generate mode: scaffold code for a caller-specified set of added components (delegates scaffolding to `azure-architecture-implementer`).
- Refactor mode: update code for modified components without touching others.
- Shared-library reconciliation: keep `src/_shared/` and `src/libs/` consistent with the active service list.
- Hygiene pass scoped to edited files only — docstrings, typed signatures, no wildcard imports.

Called automatically by `project-orchestrator`:
- After Phase 2 (drift-check follow-up to catch anything the implementer missed).
- During Update Phase U4 (sync mode with the BRD-diff-derived change list).

Never touches Bicep, `docs/requirements.md`, or the `agent_runtime` choice. All log and manifest writes flow through `project-state-manager`.

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

### repo-change-agent
Use this agent when AAF is operating against an existing GitHub or Azure DevOps repository supplied through the portal.

Typical uses:
- Review a real repository's docs, architecture files, source, tests, and infra before making changes.
- Decide whether to enhance an existing component or add a minimal new one.
- Implement the change and run focused validation inside the target repo.
- Produce `AAF-change-summary.md` for reviewers before the backend commits and opens the PR.

This agent is intentionally separated from SCM side effects. It does not create branches, push commits, or open PRs.

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
- **Use `repo-change-agent` for existing external repos under portal repo intake** — it reasons about code changes inside the cloned target repo, while the portal backend handles branch, commit, push, and PR.
- Individual agents can still be invoked standalone for targeted tasks.
- Projects created by the orchestrator live under `projects/` with full isolation per project.
- Use `factory-handoff` after `project-orchestrator` to promote the project to the shared factory portal.
- The root `QUICKSTART.md` explains how to use the orchestrator and all individual agents.

---

## Foundry Capabilities (Forward-Looking)

Each agent's YAML front matter declares `foundry_capabilities` — the tool set the agent should be granted **if/when** it is migrated from Copilot runtime to an Azure AI Foundry agent. These tokens are advisory today; the active runtime contract is the `tools` field. The tokens map to Foundry SDK constructs:

| Token | Foundry construct (.NET) | Use when... |
|---|---|---|
| `code_interpreter` | `ResponseTool.CreateCodeInterpreterTool(...)` | Agent must compute over data: cost analytics, coverage metrics, SARIF/CVE aggregation, large CSV/JSON, charts. |
| `file_search` | `ResponseTool.CreateFileSearchTool(...)` (RAG) | Output quality depends on grounding in project docs (BRDs, diagrams, templates, agent contracts, WAF refs). |
| `function_calling` | Custom function tools / MCP tools | Agent calls Azure APIs, filesystem, git, build/test runners, or sub-agents. |

### Recommended capability matrix

| Agent | code_interpreter | file_search | function_calling | Rationale |
|---|---|---|---|---|
| azure-architecture-implementer |  | ✅ | ✅ | Grounding in templates + diagrams; orchestrates sub-agents. |
| azure-project-deployer |  |  | ✅ | Pure Azure MCP / az / azd / bicep tool calls. |
| bicep-infrastructure-validator |  |  | ✅ | Filesystem + `bicep build` runner. |
| brd-to-architecture-diagram |  | ✅ | ✅ | Grounding in BRD + past diagrams; calls Draw.io MCP. |
| drawio-architecture-reader |  |  | ✅ | XML parse via filesystem tool. |
| factory-handoff |  |  | ✅ | HTTP/REST client + filesystem. |
| factory-workflow-guide |  | ✅ | ✅ | RAG over docs, templates, agent contracts. |
| lang-dotnet-implementer |  | ✅ | ✅ | RAG over factory-templates/dotnet/; runs `dotnet build/test`. |
| modernization-to-factory |  | ✅ | ✅ | Grounding in legacy repo + handoff to orchestrator. |
| production-environment-advisor |  | ✅ | ✅ | RAG over docs + Azure WAF refs; read-only Azure MCP. |
| project-cost-analyzer | ✅ |  | ✅ | Cost CSV/JSON crunching, charts, comparisons. |
| project-observability-advisor |  | ✅ | ✅ | RAG over App Insights / WAF docs; KQL via tool. |
| project-orchestrator |  |  | ✅ | Pure router (sub-agent dispatch). |
| project-state-manager |  |  | ✅ | Deterministic JSON / log writer. |
| project-traceability-advisor | ✅ | ✅ | ✅ | Coverage metrics + grounding in project files. |
| repo-change-agent |  | ✅ | ✅ | Grounding in target repo; runs build/test. |
| security-compliance-auditor |  | ✅ | ✅ | RAG over BRD compliance frameworks; Defender/azqr MCP. |
| source-code-maintainer |  | ✅ | ✅ | Drift detection grounded in diagram + BRD + code. |
| terraform-infrastructure-validator |  |  | ✅ | Filesystem + `terraform validate/fmt/plan`. |

**Strong CI candidates today**: `project-cost-analyzer`, `project-traceability-advisor` (CVE/coverage analytics also useful for `security-compliance-auditor` and `project-observability-advisor` if Foundry-migrated).

**Strong RAG candidates today**: `factory-workflow-guide`, `brd-to-architecture-diagram`, `lang-dotnet-implementer`, `source-code-maintainer`, `production-environment-advisor`.

### How orchestrators should consume these tokens
- `project-orchestrator` and `modernization-to-factory` MUST treat `foundry_capabilities` as advisory metadata — do not change runtime behavior based on the value.
- When a sub-agent is migrated to Foundry, the implementer (`lang-dotnet-implementer` or future `lang-python-implementer`) consults `foundry_capabilities` to decide which Foundry tool(s) to wire (e.g., `code_interpreter` triggers the `factory-templates/dotnet/FoundryAgentWithCodeInterpreter.cs.template` pattern).
- Unknown capability tokens MUST halt and surface a human-review item, identical to the rule for `BRD.implementation.agents[].tools`.
