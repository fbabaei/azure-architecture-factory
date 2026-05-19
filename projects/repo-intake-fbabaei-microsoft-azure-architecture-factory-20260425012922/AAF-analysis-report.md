# Repository Analysis Report

**Repository**: https://github.com/fbabaei_microsoft/azure-architecture-factory.git  
**Branch**: `AAF-live-0424182911`  
**Generated**: 2026-04-25T01:29:18.734777Z  
**Tool**: Azure Architecture Factory — automated analysis

## Repository Structure

- `Dockerfile.mcp-server`
- `Dockerfile.portal`
- `README.md`
- `assets`
- `demo`
- `diagrams`
- `docs`
- `factory-portal.html`
- `factory-projects.generated.json`
- `factory-templates`
- `infra`
- `logs`
- `outputs`
- `projects`
- `pytest.ini`
- `scripts`
- `tests`

## Code Inventory

| Language | Files |
|----------|-------|
| Markdown | 364 |
| Python | 255 |
| JSON | 52 |
| Bicep | 48 |
| YAML | 17 |
| C# | 16 |
| JavaScript | 6 |

## README Summary

<details><summary>Click to expand</summary>

# Azure Architecture Factory

Azure Architecture Factory is an AI-driven Azure delivery workspace that turns requirements into architecture, code, infrastructure, documentation, and deployment guidance. Generated services ship in **Python 3.11 / FastAPI** or **.NET 8 / ASP.NET Core**, with infrastructure in **Bicep** or **Terraform** — selectable per BRD.

## New here? Read these in order

1. [docs/QUICKSTART.md](docs/QUICKSTART.md) — the one-page "how do I use this" guide. Start here.
2. [docs/WORKFLOW_GUIDE.md](docs/WORKFLOW_GUIDE.md) — what each agent does and when to pick one.
3. [docs/BRD_CLASSIFICATION_FLOW.md](docs/BRD_CLASSIFICATION_FLOW.md) — how the factory decides whether a BRD needs the Agent Framework SDK runtime.
4. [docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md](docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md) — when a generated project should ship the Agent Framework SDK runtime vs. stay deterministic.
5. [docs/SELF_CONTAINED_SETUP.md](docs/SELF_CONTAINED_SETUP.md) — running the repo without any sibling checkouts.

Reference material:

- [docs/README.md](docs/README.md) repository overview
- [docs/COPILOT_GUIDE.md](docs/COPILOT_GUIDE.md) — the two portal AI copilots (BRD Copilot + Project Copilot), their tools, rubrics, and safety rails
- [docs/VIEW_DETAILED_ARCHITECTURE.md](docs/VIEW_DETAILED_ARCHITECTURE.md) viewing `.drawio` files on Windows
- [docs/MDR_PY_VS_DOTNET.md](docs/MDR_PY_VS_DOTNET.md) side-by-side comparison of Python vs .NET output for the same `extraction-chat` BRD
- [docs/PRD.md](docs/PRD.md) product scope and capabilities
- [docs/BRD.md](docs/BRD.md) business case and adoption goals

Key repository areas:

- [.github/agents/README.md](.github/agents/README.md) for the custom Copilot agents
- [diagrams](diagrams) for reusable architecture source artifacts
- [projects](projects) for sample project outputs and generated examples
- [infra/README.md](infra/README.md) for shared Bicep modules and deployment guidance
- [factory-templates/agent-framework/README.md](factory-templates/agent-framework/README.md) for the reusable Microsoft Agent Framework SDK runtime template
- [demo](demo) for the developer-facing portal and readiness dashboard

Current sample portfolio includes order management, storage self-service, AKS microservices, e-commerce, and the restored Fabric Medallion pipeline reference.

If you are evaluating whether the repository is ready for broader internal use, use [docs/README.md](docs/README.md) as the canonical overview and [demo/app.py](demo/app.py) for the developer portal entrypoint.

</details>

## Architecture: `.github\agents\azure-architecture-implementer.agent.md`

**Components:**

- DO NOT start by writing code blindly.
- DO NOT collapse multiple responsibilities into a single service unless the diagram clearly indicates it.
- DO NOT introduce Azure resources that are not justified by the diagram, companion notes, or explicit user goals.
- DO NOT skip documentation updates when the implementation shape changes.
- First-time scaffolding of a brand-new service folder from the diagram (Phase 2 default).
- Creating net-new Bicep modules when the diagram adds a resource that has no existing module.
- Generating tests from the BRD / diagram / test-impact handoff (Phase 3.7).
- Materializing NFRs from the BRD into executable code (rate limiting, retry, audit logging, middleware).
- Creating initial project documentation (README, DEPLOY, QUICKSTART, service-level READMEs, `docs/scaling.md`).
- `incremental` additions of new services or new modules driven by Phase 2.5 gap lists.
- Modifying files inside an already-scaffolded service → `source-code-maintainer add-to-service` or `refactor`.
- Bicep syntax fixes or scalability reviews of existing modules → `bicep-infrastructure-validator`.

## Architecture: `.github\agents\bicep-infrastructure-validator.agent.md`

**Components:**

- DO NOT delete files; only edit and fix.
- DO NOT remove functionality; only correct syntax and logical errors.
- DO NOT deploy infrastructure; this is validation and fixing only.
- DO NOT introduce breaking changes; maintain backward compatibility.
- ALWAYS validate fixes by re-checking errors after edits.
- If `iac_tool == "disabled"` (the caller set `generation_options.generateInfra=false`), STOP and respond:
- If `iac_tool == "terraform"`, STOP and respond:
- If `iac_tool` is any other value, STOP and escalate to the orchestrator with a blocker.
- Bicep / `.bicepparam` syntax validation and auto-fix for every file under `infra/`.
- Module reference wiring, output-to-input correctness, decorator correctness, path resolution.
- Infra-layer scalability fixes (Phase 2.8 `scalability-review` mode).
- Infra-layer security fixes dispatched by `security-compliance-auditor` (Phase 2.6).

## Architecture: `.github\agents\brd-to-architecture-diagram.agent.md`

**Components:**

- DO NOT guess Azure services; derive every component from stated requirements.
- DO NOT create overly complex diagrams; include only what the requirements justify.
- ALWAYS use the transactional workflow for diagrams with more than 3 components.
- ALWAYS call `search-shapes` BEFORE calling `add-cells` — use returned `shape_name` values for all Azure service vertices.
- **REQUIRE Azure icons**: Every vertex representing an Azure service MUST use a `shape_name` from `search-shapes` (e.g., `Container Apps`, `Cosmos DB`, `Key Vault`). DO NOT use generic rectangles (`rounded=1;whiteSpace=wrap`).
- ALWAYS save the exported XML to `diagrams/<name>.drawio` and notes to `diagrams/<name>.md`.
- ALWAYS follow left-to-right primary flow and place cross-cutting services at the bottom.
- DO NOT draw edges between cross-cutting services or from main-flow to cross-cutting services.
- [Label 1] — <Azure service if identifiable>
- [Label 2] — ...
- **Problem statement** (what the system does)
- **Users** (who interacts with it)

## Architecture: `.github\agents\drawio-architecture-reader.agent.md`

**Components:**

- DO NOT edit files.
- DO NOT recommend code structures that are not grounded in the diagram or companion notes.
- DO NOT return generic architecture advice when specific components can be extracted.
- Diagram summary.
- Component inventory grouped by type.
- Data and control flows.
- Suggested microservice boundaries.
- Azure resource mapping candidates.
- Open questions or missing detail.

## Architecture: `.github\agents\terraform-infrastructure-validator.agent.md`

**Components:**

- DO NOT delete files; only edit and fix.
- DO NOT remove functionality; only correct syntax and logical errors.
- DO NOT deploy infrastructure; this is validation and fixing only.
- DO NOT introduce breaking changes; maintain backward compatibility.
- DO NOT run `terraform apply` or `terraform destroy` — validation only.
- ALWAYS validate fixes by re-running `terraform validate` and `terraform fmt -check` after edits.
- If `iac_tool == "disabled"` (the caller set `generation_options.generateInfra=false`), STOP and respond:
- If `iac_tool == "bicep"` (or `iac_tool` is absent and `infra/main.bicep` exists), STOP and respond:
- If `iac_tool` is any other value, STOP and escalate to the orchestrator with a blocker.
- Terraform HCL syntax validation and auto-fix for every `*.tf` file under `infra/`.
- Provider pinning correctness (`required_version`, `required_providers`).
- Variable / output / resource reference correctness.

## Architecture: `diagrams\azure-ai-foundry-architecture.drawio`

**Components:**

- Azure AI Foundry - Agentic Application Architecture
- Azure AI Foundry Solution Architecture
- COMPUTE
- Agent Service (Python - Port 8000)
- AI & DATA SERVICES
- AI Search
- Blob Storage
- Cosmos DB
- Key Vault
- Azure AI Foundry
- App Insights
- SECURITY & IDENTITY

**Relationships:**

- Agent Service (Python - Port 8000) -> AI Search
- Agent Service (Python - Port 8000) -> Blob Storage
- Agent Service (Python - Port 8000) -> Cosmos DB
- Agent Service (Python - Port 8000) -> Key Vault
- Agent Service (Python - Port 8000) -> Azure AI Foundry
- Agent Service (Python - Port 8000) -> App Insights

*Parsing: draw.io XML parsed, 6 edge(s) extracted*

## Architecture: `diagrams\azure-ai-foundry-architecture.md`

**Components:**

- "Azure Container Apps (ACA) Environment"
- "`Azure AI Foundry (Azure AI Services)`"
- "`AI Search (Azure AI Search)`"
- "`Blob Storage (Azure Storage Account)`"
- "`Cosmos DB (Azure Cosmos DB)`"
- "`Key Vault (Azure Key Vault)`"

## Architecture: `diagrams\azure-ai-foundry-waf-architecture.drawio`

*Parsing: draw.io XML parsed*

## Architecture: `diagrams\azure-apim-containerapps-cosmos.drawio`

*Parsing: draw.io XML parsed*

## Architecture: `diagrams\azure-eventgrid-cv-new.drawio`

*Parsing: draw.io XML parsed*

---

> This report was generated automatically by the Azure Architecture Factory.
> Review and amend before merging to your main branch.
