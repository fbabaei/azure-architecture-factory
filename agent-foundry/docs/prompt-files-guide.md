# Prompt Files Guide

The files in `.github/prompts/` are the user-facing slash-command entry points for Azure AI Agent Foundry. They help users start in the right mode without opening the raw agent files first.

Prompt files are different from agent files:

| File type | Location | Purpose |
| --- | --- | --- |
| Prompt files | `.github/prompts/*.prompt.md` | Define the slash command users invoke, the default handling agent, allowed tools, input hint, and expected answer shape. |
| Agent files | `.github/agents/*.agent.md` | Define the specialist behavior, boundaries, routing rules, and working style for a reusable custom agent. |

Use prompt files when the user needs a guided starting point. Use agent files when you need to inspect or improve the behavior of the specialist that performs the work.

## Prompt Entry Points

| Prompt | Use When | Routes To | Expected Output |
| --- | --- | --- | --- |
| `/find-ai-agent` | You know the task, service, app scenario, or learning goal, but do not know which agent to use. | Azure AI Agent Foundry Orchestrator | Recommended agent or agents, mode, fit rationale, required configuration or source references, and next action. |
| `/browse-ai-agent-foundry` | You want to see what exists in the catalog by area, capability, blueprint, or shared platform concern. | Azure AI Agent Foundry Orchestrator | Concise grouped catalog view: orchestrators, application blueprints, shared platform specialists, and source references. |
| `/learn-ai-capability` | You want a guided Azure AI learning route backed by the source repositories under `external/`. | Azure AI Learning Orchestrator | Matched learning area, source path, prerequisites, learning sequence, hands-on lab or application follow-up, and cleanup or cost reminders. |
| `/design-ai-agent-solution` | You want to design a real application using reusable Azure AI application agents. | Azure AI Application Orchestrator | Selected blueprints, architecture/API/data/configuration/test/evaluation/UX handoffs, configuration contract, input/output contracts, integration pattern, safety/auth/security/monitoring/operations considerations, validation checks, and implementation order. |
| `/design-from-architecture` | You have Markdown architecture notes, Mermaid or PlantUML text, a diagram export, ADRs, component notes, or a pasted architecture description and want to convert it into a Foundry agent design handoff. | Azure AI Application Orchestrator | Architecture evidence summary, verified elements, assumptions, unsupported inferences, architecture-to-agent mapping, selected blueprints, design handoffs, Microsoft Agent Framework fit, validation checks, and open decisions. |
| `/implement-from-brd-prd` | You have a BRD, PRD, feature brief, requirements file, or pasted requirements and want to turn it into an implementation-ready Foundry agent plan. | Azure AI Application Orchestrator | BRD/PRD evidence summary, verified requirements, requirement-to-agent mapping, selected blueprints, handoffs, Microsoft Agent Framework fit, phased implementation plan, first bounded implementation step, validation checks, and open decisions. |

## Choosing The Right Prompt

Start with `/find-ai-agent` when the request is still broad or ambiguous.

Start with `/browse-ai-agent-foundry` when the user wants to explore the catalog before choosing a direction.

Start with `/learn-ai-capability` when the user asks for study help, labs, modules, prerequisites, or a learning sequence.

Start with `/design-ai-agent-solution` when the user has an application scenario and wants a practical agent-based architecture or implementation plan.

Start with `/design-from-architecture` when the user already has architecture input, especially Markdown architecture notes, Mermaid, PlantUML, draw.io or Visio exports, ADRs, component lists, data-flow notes, or a diagram summary.

Start with `/implement-from-brd-prd` when the user already has product or business requirements and wants an Azure Architecture Factory-style intake that converts the BRD/PRD into Foundry agent implementation work.

For application designs, ask for a Microsoft Agent Framework fit assessment when the app may need a runnable agent runtime, tools or actions, stateful workflows, Microsoft Foundry lifecycle support, evaluation, tracing, debugging, or deployment. Keep the simpler service or SDK path when the user only needs learning guidance, a one-off API call, a static catalog, or design documentation.

## Example User Paths

### Find The Right Agent

```text
/find-ai-agent I am building an app that extracts invoice fields and lets users search over them.
```

Expected route:

- Document Processing App Agent
- RAG Search App Agent, if search or question answering is required
- Auth Config Agent and Foundry Integration Agent, if environment setup is part of the work

### Browse Before Choosing

```text
/browse-ai-agent-foundry application blueprints
```

Use this when a user wants to compare options such as vision chat, image generation, video generation, content understanding, RAG search, and document processing.

### Learn A Capability

```text
/learn-ai-capability Azure AI Search vector and hybrid retrieval
```

Use this when the goal is learning first. The output should point to relevant source material, prerequisites, lab flow, and a follow-up application path.

### Design An Application Solution

```text
/design-ai-agent-solution Build a support assistant that answers questions from product images and policy documents.
```

Use this when the user is ready to combine agents into a design. The output should describe selected blueprints, architecture handoffs, API and integration contracts, data and storage decisions, configuration and environment contracts, test and evaluation strategy, UX and human workflow needs, integration sequence, safety checks, auth needs, security review needs, monitoring and evaluation signals, operations readiness, and validation steps.

If the scenario looks like a real runnable agent app, the output should also say whether Microsoft Agent Framework is a good fit and what implementation handoff would be needed.

### Design From Architecture Markdown Or Diagram Text

```text
/design-from-architecture docs/customer-support-architecture.md
```

Use this when a user wants to start from an existing architecture artifact instead of a blank scenario or BRD/PRD. Markdown is the preferred input format, but Mermaid, PlantUML, draw.io or Visio export text, ADRs, component lists, data-flow notes, and pasted diagram descriptions are also valid.

The user should replace placeholder text with a real workspace file path or pasted architecture content. The shortest useful form is:

```text
/design-from-architecture <workspace file path or pasted Markdown/Mermaid/PlantUML/export text>
```

For pasted Markdown, put the content directly after the slash command:

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

The browser can generate a longer prompt that appends handling instructions such as extracting verified architecture elements, mapping components and flows to specialists or blueprints, assessing Microsoft Agent Framework fit, and not inventing components, Azure resources, endpoints, model deployments, security boundaries, test results, or implementation evidence. That longer form is valid and recommended when the user wants evidence discipline called out explicitly.

The output should extract verified architecture elements, map components and flows to the right Foundry agents, identify unsupported inferences, select blueprints only when supported, assess Microsoft Agent Framework fit, and prepare a design-first handoff sequence.

If the input is only an image and the agent cannot inspect image contents directly, the prompt should ask for Markdown notes, Mermaid or PlantUML text, OCR output, exported diagram text, or a user-provided summary instead of inventing components, services, data flows, security boundaries, Azure resources, endpoints, or validation evidence.

### Implement From A BRD Or PRD

```text
/implement-from-brd-prd docs/customer-support-prd.md
```

Use this when a user wants to start from a BRD, PRD, feature brief, issue, or requirements summary instead of a blank app idea. The output should extract verified requirements, map each requirement to the right Foundry agent, identify missing decisions, select blueprints only when supported, assess Microsoft Agent Framework fit, and prepare the first bounded step for Application Implementation Validation Agent.

If the document is incomplete or unavailable, the prompt should say what is missing instead of inventing requirements, Azure resources, endpoints, model deployments, or validation evidence.

## Maintenance Notes

When adding or changing a prompt file:

1. Keep the prompt focused on one entry-point job.
2. Use a clear `name`, `description`, `agent`, `tools`, and `argument-hint` in frontmatter.
3. Route broad discovery prompts to the Foundry orchestrator.
4. Route learning prompts to the learning orchestrator.
5. Route application design prompts to the application orchestrator.
6. Keep prompt outputs evidence-based. If a prompt does not have enough workspace, source, Azure, or user-provided context, it should say what is missing instead of making up details.
7. Run validation from the repo root:

```powershell
pwsh -File scripts/validate-agent-zone.ps1
```
