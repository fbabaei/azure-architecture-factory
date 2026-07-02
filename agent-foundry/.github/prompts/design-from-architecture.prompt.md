---
name: "Design From Architecture"
description: "Convert an application architecture diagram, Markdown architecture notes, Mermaid or PlantUML text, draw.io or Visio export, or pasted architecture description into an Azure AI Agent Foundry design and implementation handoff."
agent: "Azure AI Application Orchestrator"
tools: [read, search, agent]
argument-hint: "Provide a Markdown architecture file path, Mermaid or PlantUML text, diagram export description, or pasted component/data-flow notes."
---
Use Azure AI Agent Foundry agents to convert the supplied application architecture artifact into an evidence-based design handoff.

Preferred input is Markdown that describes the architecture. You can also use Mermaid, PlantUML, draw.io or Visio export text, architecture decision records, component lists, data-flow notes, deployment notes, or a pasted diagram description.

Use one of these input forms:

```text
/design-from-architecture docs/customer-support-architecture.md
```

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

The browser-generated prompt may append handling instructions after the file path or pasted architecture content. Treat those instructions as guardrails for evidence discipline and routing.

Treat the artifact as source evidence, not as complete truth. Extract only what is present, label assumptions, and ask for missing decisions when design or implementation would otherwise require invention.

Process:
1. Identify the architecture source: workspace file path, pasted Markdown, Mermaid, PlantUML, diagram export text, or summarized diagram description.
2. Extract verified architecture elements: actors, channels, components, services, agents, Azure services, data stores, APIs, events, tools, integrations, deployment units, environments, trust boundaries, data flows, control flows, quality attributes, constraints, and risks.
3. Separate verified facts from assumptions, examples, unsupported inferences, and open decisions.
4. Convert the architecture into design work owned by the relevant Foundry agents:
   - Azure AI Application Orchestrator for overall routing and design synthesis.
   - Architecture & Design Agent for components, boundaries, request flows, data flows, and design decisions.
   - API & Integration Contract Agent for APIs, tool contracts, events, schemas, errors, retries, and downstream assumptions.
   - Data & Storage Design Agent for data stores, indexes, retention, embeddings, generated assets, audit, and privacy.
   - Configuration & Environment Contract Agent for environments, settings, secrets references, endpoint placeholders, and preflight checks.
   - Test & Evaluation Strategy Agent for architecture validation, AI quality checks, mocks, datasets, and acceptance criteria.
   - UX & Human Workflow Agent for user journeys, review states, fallbacks, confidence handling, and feedback loops.
   - Security & Compliance Agent for trust boundaries, identity, secrets, RBAC, data protection, and compliance gaps.
   - Monitoring & Evaluation Agent for telemetry, tracing, evaluation signals, alerts, and production quality monitoring.
   - Operations Readiness Agent for release readiness, runbooks, rollback, quotas, cost guardrails, and support handoff.
   - Application Planning Companion Agent for tracking decisions and converting the design into bounded steps.
   - Application Implementation Validation Agent for execution, command running, tests, local server checks, and validation evidence.
5. Select application blueprint agents only when the architecture supports them.
6. Assess whether Microsoft Agent Framework fits the design based on runtime, tools/actions, state, workflow, tracing, evaluation, deployment, or Foundry lifecycle needs.
7. Produce a design-first plan with architecture traceability and validation gates.

Return:
- architecture source and evidence summary
- verified architecture elements and assumptions
- unsupported inferences and open decisions
- architecture-to-agent mapping
- selected blueprints and why
- architecture/API/data/configuration/UX/test handoffs
- security, safety, monitoring, and operations handoffs
- Microsoft Agent Framework fit assessment
- design plan and implementation handoff sequence
- bounded first design or implementation step
- validation checks and acceptance criteria

If the input is only an image and you cannot inspect image contents directly, ask for a Markdown description, Mermaid or PlantUML text, OCR output, exported diagram text, or a user-provided summary. Do not invent components, services, data flows, Azure resources, endpoints, model deployments, security boundaries, test results, command output, or implementation evidence.