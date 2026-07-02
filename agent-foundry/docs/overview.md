# Azure AI Agent Foundry Overview

Azure AI Agent Foundry is a reusable support zone for AI engineering work in VS Code. It gives users a catalog of custom agents that can either guide learning or help application developers select and configure reusable AI capabilities for real applications.

## Purpose

The Foundry is designed for two audiences:

- **Learners** who want guided paths through Azure AI concepts, modules, and labs.
- **Application developers** who want preconfigured agent blueprints that can be adapted into application designs.

The same catalog supports both audiences. Learning agents stay close to module and lab source material. Application agents turn the same knowledge into reusable patterns, configuration contracts, integration guidance, and validation checks.

## Source Material

The current implementation references two source repositories under `external/`:

| Source | Local Path | Used For |
| --- | --- | --- |
| MicrosoftLearning/mslearn-ai-vision | `external/mslearn-ai-vision` | Vision-enabled chat, image generation, Sora video generation, Content Understanding |
| kennethleungty/Azure-AI-Engineer-Associate-Notes | `external/Azure-AI-Engineer-Associate-Notes` | Broad Azure AI engineering coverage across AI services, vision, NLP, search, documents, and Azure OpenAI |

The source repositories are local dependencies and are ignored by this project's `.gitignore`.

## Agent Layers

The Foundry uses a layered agent model.

### Top-Level Orchestration

**Azure AI Agent Foundry Orchestrator** receives broad requests, searches the catalog, identifies whether the user needs learning or application support, and routes to the right agent.

### Mode Orchestration

**Azure AI Learning Orchestrator** handles study, labs, modules, and learning routes.

**Azure AI Application Orchestrator** handles application design, reusable agent selection, configuration contracts, and integration planning.

### Application Design Specialists

Application design specialists handle early design work for new or underspecified applications:

- Architecture and component boundaries
- API, event, webhook, tool, and integration contracts
- Data, storage, indexing, metadata, retention, and audit patterns
- Configuration contracts, environment variables, feature flags, and preflight validation
- Build-time test strategy, AI evaluation planning, mocks, datasets, and acceptance criteria
- User journeys, review queues, confidence thresholds, fallback states, and feedback loops

### Capability Orchestration

Capability orchestrators cover the main Azure AI engineering areas:

- Azure AI Services foundations
- Vision solutions
- NLP solutions
- Knowledge mining and Azure AI Search
- Document Intelligence
- Generative AI and Azure OpenAI

### Shared Specialists

Shared specialists handle concerns that appear across many Azure AI solutions:

- Foundry project and deployment integration
- Authentication and environment configuration
- Responsible AI, safety, and moderation
- Security posture, threat modeling, compliance readiness, and data protection
- Monitoring, telemetry, tracing, alerting, evaluation, and quality signals
- Operations readiness, runbooks, rollback, incident response, quota, and cost guardrails

### Application Blueprints

Application blueprint agents help developers plug AI capabilities into real app designs:

- Vision Chat App Agent
- Image Generation App Agent
- Video Generation App Agent
- Content Understanding Metadata Agent
- RAG Search App Agent
- Document Processing App Agent

### Step-By-Step Assistant Support

The Foundry also includes companion agents that help users move through the guides instead of only choosing a route once.

| Companion | Use when | Boundary |
| --- | --- | --- |
| Azure AI Learning Orchestrator | A user wants guided learning steps, checkpoints, source paths, and follow-up prompts. | It guides learning and lab sequencing; it does not invent source content or claim a lab was completed. |
| Application Planning Companion Agent | A user wants an assistant to tag along with application steps, track decisions, manage handoffs, and prepare bounded implementation tasks. | It may write planning artifacts, but it does not run commands or validations. |
| Application Implementation Validation Agent | A user has an approved bounded step that needs file edits, commands, tests, local servers, or validation evidence. | It executes only the named step and reports evidence; unclear planning goes back to the planning companion. |

## Discovery Model

The registry file `.github/agent-zone/ai-agent-index.json` is the machine-readable source of truth. It includes each agent's path, audience, level, capabilities, keywords, and source references.

The catalog file `.github/agent-zone/catalog.md` is the human-readable browse view.

The browser file `browser/index.html` is the local visual catalog. It embeds the MVP registry data so it can be opened directly from disk, while the JSON registry remains the authoritative machine-readable source for automation.

The prompt files in `.github/prompts/` provide the user-facing entry points:

- `/find-ai-agent`
- `/browse-ai-agent-foundry`
- `/design-ai-agent-solution`
- `/design-from-architecture`
- `/implement-from-brd-prd`
- `/learn-ai-capability`

For user-facing guidance on when to choose each entry point, see [Prompt Files Guide](prompt-files-guide.md).

## How Routing Works

1. The user describes a task, app scenario, learning goal, or Azure service.
2. The top orchestrator classifies the request as learning, application, or mixed.
3. The orchestrator searches the registry and catalog.
4. The request is routed to a capability orchestrator, shared specialist, or application blueprint.
5. The selected agent returns the next action, required configuration, source references, and validation guidance.

## Example Requests

| User Request | Expected Route |
| --- | --- |
| "I want to add image-aware chat to a retail app." | Vision Chat App Agent plus Auth Config Agent |
| "Help me learn Azure AI Search knowledge mining." | Azure AI Learning Orchestrator to Knowledge Mining Search Orchestrator |
| "I need an agent for extracting fields from invoices." | Document Processing App Agent |
| "I have a new AI app idea but need components and flow first." | Architecture & Design Agent plus Azure AI Application Orchestrator |
| "I have a PRD and want to turn it into implementation steps." | `/implement-from-brd-prd` to Azure AI Application Orchestrator plus design, blueprint, and validation handoffs |
| "I have Markdown architecture notes or a diagram and want to turn it into a design." | `/design-from-architecture` to Azure AI Application Orchestrator plus architecture, contract, data, security, monitoring, and implementation handoffs |
| "Define the API contract and retry behavior for this agent app." | API & Integration Contract Agent |
| "Where should this app store documents, embeddings, metadata, and audit logs?" | Data & Storage Design Agent plus Security & Compliance Agent |
| "Define the `.env` contract and validation rules before implementation." | Configuration & Environment Contract Agent plus Auth Config Agent |
| "What tests and evaluations should block this AI app from shipping?" | Test & Evaluation Strategy Agent plus Responsible AI Safety Agent |
| "How should humans review low-confidence AI outputs?" | UX & Human Workflow Agent plus Monitoring & Evaluation Agent |
| "Which endpoint should my image generation app use?" | Image Generation App Agent plus Auth Config Agent |
| "My Sora workflow needs polling and download handling." | Video Generation App Agent |
| "What security checks should block launch for this app?" | Security & Compliance Agent plus Auth Config Agent and Responsible AI Safety Agent |
| "How should I monitor quality, latency, and unsafe outputs?" | Monitoring & Evaluation Agent plus Responsible AI Safety Agent |
| "Is this agent app ready for production support?" | Operations Readiness Agent plus Monitoring & Evaluation Agent |

## Maintenance Model

When adding agents:

1. Create a focused `.agent.md` file under `.github/agents/`.
2. Add a registry entry in `.github/agent-zone/ai-agent-index.json`.
3. Add human-readable catalog information in `.github/agent-zone/catalog.md`.
4. Include a grounding and uncertainty policy that tells the agent to use available evidence, state missing inputs, and avoid inventing resource names, file paths, command output, or source citations.
5. Run `pwsh -File scripts/validate-agent-zone.ps1`.

When adding prompts:

1. Create a `.prompt.md` file under `.github/prompts/`.
2. Give it a clear `description`, `name`, and `agent` frontmatter field.
3. Run validation.

## Current Scope

This MVP is declarative. It provides VS Code custom agents, prompts, registry metadata, and documentation. It does not yet generate runnable Microsoft Foundry hosted agents or application code by default.

Future phases can add:

- generated runnable templates for selected application blueprints
- evaluation datasets and batch checks
- richer search UI
- CI validation for agent metadata
- packaging for reuse across workspaces
