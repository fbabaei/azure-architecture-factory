# Quick Start Guide

This guide gets Azure AI Agent Foundry ready for use in VS Code and shows how to find, browse, and use the agents.

## 1. Open The Project

Open this folder in VS Code:

```text
/dev/workspace/azure-ai-agent-foundry
```

The custom agents and prompts live under `.github/`, so VS Code should discover them when this folder is the active workspace.

## 2. Restore Source Repositories

The `external/` repositories are ignored by git. If they are missing, clone them from the project root:

```powershell
git clone https://github.com/MicrosoftLearning/mslearn-ai-vision.git external/mslearn-ai-vision
git clone https://github.com/kennethleungty/Azure-AI-Engineer-Associate-Notes.git external/Azure-AI-Engineer-Associate-Notes
```

On Windows, if the second clone has long-path checkout issues, run:

```powershell
Set-Location external/Azure-AI-Engineer-Associate-Notes
git config core.longpaths true
git checkout -f HEAD
Set-Location ../..
```

## 3. Validate The Foundry

Run validation from the project root:

```powershell
pwsh -File scripts/validate-agent-zone.ps1
```

Expected result:

```text
Catalog        : Azure AI Agent Foundry
Version        : 0.1.0
RegistryAgents : 29
AgentFiles     : 29
PromptFiles    : 6
Browser        : Present
Status         : Valid
```

## 4. Use The Prompt Entry Points

Open VS Code Chat and use one of these prompts.

Use this quick decision table when choosing where to start:

| Prompt | Best Starting Point For |
| --- | --- |
| `/find-ai-agent` | Choosing the right agent from a task, service, app scenario, or learning goal. |
| `/browse-ai-agent-foundry` | Exploring the full catalog by area, blueprint, capability, or shared platform concern. |
| `/learn-ai-capability` | Starting a guided learning route from the source repositories under `external/`. |
| `/design-ai-agent-solution` | Designing a real app with reusable agent blueprints, architecture handoffs, API/data/configuration contracts, UX workflow, testing, evaluation, safety, auth, security, monitoring, operations, and validation. |
| `/design-from-architecture` | Converting Markdown architecture notes, Mermaid/PlantUML text, diagram exports, or pasted architecture descriptions into a design handoff owned by Foundry agents. |
| `/implement-from-brd-prd` | Turning a BRD, PRD, feature brief, or requirements file into a requirement-to-agent implementation plan. |

For a fuller explanation, see [Prompt Files Guide](prompt-files-guide.md).

### Find An Agent

Use:

```text
/find-ai-agent
```

Example requests:

```text
I need an agent for extracting metadata from product images.
```

```text
Which agent helps me build RAG over enterprise documents?
```

```text
I need help configuring Azure OpenAI endpoint settings.
```

### Browse The Catalog

Use:

```text
/browse-ai-agent-foundry
```

Example requests:

```text
Show me all application blueprint agents.
```

```text
Browse agents for vision and Content Understanding.
```

### Design An Application Agent Solution

Use:

```text
/design-ai-agent-solution
```

Example request:

```text
Design an agent setup for an app that accepts PDF invoices, extracts fields, indexes the results, and lets users ask questions over them.
```

Expected output includes:

- selected app agents
- configuration contract
- input/output contract
- integration pattern
- Microsoft Agent Framework fit assessment when a runnable agent runtime or workflow framework may help
- safety and auth considerations
- security, monitoring, and operations readiness considerations when production-facing
- validation checks

### Learn An AI Capability

Use:

```text
/learn-ai-capability
```

Example requests:

```text
Help me learn Azure AI Search knowledge mining.
```

```text
Guide me through the vision-enabled chat lab.
```

## 5. Browse Files Directly

Useful files:

- `browser/index.html` - local AAF browser for search, filters, agent details, and configuration previews
- `.github/agent-zone/catalog.md` - human-readable catalog
- `.github/agent-zone/ai-agent-index.json` - machine-readable routing registry
- `.github/agents/` - custom agent definitions
- `.github/prompts/` - VS Code chat prompt entry points
- `docs/overview.md` - architecture and operating model
- `docs/quick-start.md` - this guide

## 6. Common Workflows

### Workflow: Browse Visually

1. Open `browser/index.html`.
2. Search by task, service, model, or application scenario.
3. Filter by audience, agent level, or capability.
4. Inspect the configuration contract and activation prompt.
5. Open the matching `.agent.md` file or run the recommended prompt in VS Code Chat.

### Workflow: Choose An Agent For An App

1. Run `/find-ai-agent`.
2. Describe the app scenario, inputs, outputs, and target Azure service.
3. Review the recommended blueprint agents.
4. Run `/design-ai-agent-solution` for configuration and integration details.
5. Use shared specialists for Foundry, auth, and safety details.

### Workflow: Use An Assistant Agent Through The Steps

Use companion agents when a user wants help moving through a guide one step at a time.

| Need | Assistant agent | Example request |
| --- | --- | --- |
| Guided learning steps | Azure AI Learning Orchestrator | `Azure AI Learning Orchestrator, walk me through the Azure AI Search learning path one step at a time and wait for my checkpoint after each step.` |
| Application planning without execution | Application Planning Companion Agent | `Application Planning Companion Agent, tag along with this build, track the current step, decisions, handoff agents, validation checks, and open questions.` |
| File changes, commands, tests, or validation evidence | Application Implementation Validation Agent | `Application Implementation Validation Agent, implement the approved current step and run the focused validation check.` |

Keep planning and execution separate. The planning companion can write trackers, clarify ownership, and prepare bounded tasks, but it should hand off command execution and validation to Application Implementation Validation Agent.

### Workflow: Start From A BRD Or PRD

1. Open `browser/index.html`.
2. Use the BRD/PRD Implementation Intake section to paste requirements or reference a workspace file path.
3. Copy the generated `/implement-from-brd-prd` prompt into VS Code Chat.
4. Review the requirement-to-agent mapping, phased implementation plan, and missing decisions.
5. Hand the first bounded implementation step to Application Implementation Validation Agent when files, placeholders, acceptance criteria, and validation checks are clear.

### Workflow: Start From Architecture Notes Or A Diagram

1. Open `browser/index.html`.
2. Use the Architecture To Design Intake section to paste Markdown architecture notes, Mermaid or PlantUML text, diagram export text, or a workspace file path.
3. Copy the generated `/design-from-architecture` prompt into VS Code Chat.
4. Review the verified architecture elements, architecture-to-agent mapping, design handoffs, unsupported inferences, and open decisions.
5. Hand the first bounded design or implementation step to the planning or implementation validation agent when files, placeholders, acceptance criteria, and validation checks are clear.

Recommended short form:

```text
/design-from-architecture <workspace file path or pasted Markdown/Mermaid/PlantUML/export text>
```

Example with a workspace file:

```text
/design-from-architecture docs/customer-support-architecture.md
```

Example with pasted Markdown:

```text
/design-from-architecture
# Customer Support Assistant Architecture

## Components
- Web chat UI
- Azure AI Agent for support triage
- Azure AI Search index over support articles
- Human escalation queue

## Flows
- User asks a question in chat
- Agent retrieves grounding content from Azure AI Search
- Low-confidence answers route to human review
```

The browser-generated prompt may include additional instruction text after the architecture input. Keep that text when you want stronger guardrails: it tells the agent to extract only verified elements, map components and flows to Foundry agents, assess Microsoft Agent Framework fit, and avoid inventing components, Azure resources, endpoints, model deployments, security boundaries, test results, or implementation evidence.

### Workflow: Learn Then Apply

1. Run `/learn-ai-capability`.
2. Complete the recommended learning route or lab.
3. Run `/design-ai-agent-solution` with your real app scenario.
4. Ask the selected application blueprint for a plug-in configuration contract.

### Workflow: Add A New Agent

1. Add a focused `.agent.md` file under `.github/agents/`.
2. Add a matching entry to `.github/agent-zone/ai-agent-index.json`.
3. Update `.github/agent-zone/catalog.md`.
4. Run validation.

## 7. Troubleshooting

### Prompts Do Not Appear In VS Code Chat

Check that the workspace root is `azure-ai-agent-foundry` and that prompt files are under `.github/prompts/`.

### Validation Says Source Repositories Are Missing

Re-run the clone commands in step 2.

### Validation Says An Agent Path Is Missing

Check that every registry `path` points to an existing `.agent.md` file.

### An Agent Is Not Selected For A Relevant Query

Improve the agent `description` and registry `keywords`. VS Code discovery depends heavily on clear, keyword-rich descriptions.

## 8. First Recommended Test

Try this in VS Code Chat:

```text
/find-ai-agent I am building an app that lets users upload images and automatically creates searchable descriptions and tags.
```

Expected route:

- Content Understanding Metadata Agent
- Auth Config Agent
- Foundry Integration Agent, if a Foundry resource or analyzer setup is needed
