# Azure AI Agent Foundry Application Implementation

Use this guide as the application-side companion to the learning paths. It shows how to move from an idea to a minimal working AI agent application by using the Azure AI Agent Foundry orchestrators, blueprint agents, and shared platform specialists.

## Recommended Agents

Start with the primary application orchestrator:

| Agent | Use when |
| --- | --- |
| Azure AI Application Orchestrator | You need to design an app with reusable Azure AI agents, choose blueprint agents, define configuration, and plan integration. |
| Application Planning Companion Agent | You have an app design and need help managing steps, tracking decisions, coordinating handoffs, or maintaining planning artifacts without terminal execution. |
| Application Implementation Validation Agent | You need to implement bounded steps, run terminal commands, execute tests, start local servers, or collect validation evidence. |

## How Assistant Agents Help Through This Guide

Use assistant agents as step-by-step companions rather than only as one-time routers.

| User need | Use this agent | What it should do |
| --- | --- | --- |
| Walk through the application steps in order | Application Planning Companion Agent | Track the current step, decisions, owners, handoff agents, validation checks, and open questions. |
| Turn a design step into an implementation-ready task | Application Planning Companion Agent | Define target files, placeholders, acceptance criteria, validation command, and remaining blockers without running commands. |
| Execute an approved bounded step | Application Implementation Validation Agent | Edit files, run focused commands, start local servers when needed, collect validation evidence, and report remaining issues. |
| Resolve a specialist decision | The relevant design or shared specialist | Produce the architecture, API, data, configuration, UX, test, safety, security, monitoring, or operations handoff for the planning companion. |

Recommended starter prompt:

```text
Application Planning Companion Agent, walk me through this application implementation guide one step at a time. Track the current step, decisions, owner agents, handoffs, validation checks, and open questions. Do not run commands; prepare execution handoffs for Application Implementation Validation Agent when needed.
```

When a step is ready for execution, hand it off explicitly:

```text
Application Implementation Validation Agent, execute the approved current step from the planning tracker, edit only the named files, run the focused validation command, and summarize evidence plus remaining issues.
```

Use these application design specialists before implementation when the app is new or underspecified:

| Specialist | Use when |
| --- | --- |
| Architecture & Design Agent | You need components, boundaries, request flows, data flows, and design decisions before choosing implementation tasks. |
| API & Integration Contract Agent | You need API, CLI, event, webhook, tool, or service contracts with schemas, errors, retries, and integration assumptions. |
| Data & Storage Design Agent | You need storage, indexing, metadata, generated asset, retention, privacy, or audit patterns. |
| Configuration & Environment Contract Agent | You need `.env`, settings, endpoint placeholders, feature flags, environment-specific values, or validation rules. |
| Test & Evaluation Strategy Agent | You need test layers, mocks, manual validation, AI quality evaluations, regression datasets, or acceptance criteria. |
| UX & Human Workflow Agent | You need user journeys, review queues, confidence thresholds, fallback states, feedback capture, or human-in-the-loop flows. |

Then choose one application blueprint agent:

| Scenario | Agent |
| --- | --- |
| Ask questions about uploaded images | Vision Chat App Agent |
| Generate images from prompts | Image Generation App Agent |
| Generate or remix videos | Video Generation App Agent |
| Extract structured metadata from images | Content Understanding Metadata Agent |
| Build a search-grounded assistant | RAG Search App Agent |
| Extract fields from PDFs, forms, or invoices | Document Processing App Agent |

Use these shared specialists as needed:

| Specialist | Use when |
| --- | --- |
| Foundry Integration Agent | You need Foundry project, model deployment, quota, endpoint, or deployment-name guidance. |
| Auth Config Agent | You need local auth, Microsoft Entra ID, DefaultAzureCredential, `.env`, managed identity, or endpoint validation guidance. |
| Responsible AI Safety Agent | You need content safety, moderation, prompt-injection handling, output filtering, or evaluation checks. |
| Security & Compliance Agent | You need threat modeling, data protection, secrets, RBAC, network exposure, or compliance readiness review. |
| Monitoring & Evaluation Agent | You need telemetry, tracing, Azure Monitor/Application Insights signals, alerting, evaluation checks, or quality monitoring. |
| Operations Readiness Agent | You need production readiness, runbooks, rollback, support handoff, incident response, quota, or cost guardrails. |

## Implementation Order

1. Pick the application scenario or provide a BRD/PRD or architecture artifact.
2. Extract verified requirements and map them to Foundry agents when a BRD, PRD, feature brief, or requirements file exists.
3. Extract verified architecture elements and map them to Foundry agents when Markdown architecture notes, Mermaid, PlantUML, diagram exports, ADRs, component lists, or data-flow notes exist.
4. Use Architecture & Design Agent when the app needs components, boundaries, or flow decisions.
5. Use API & Integration Contract Agent when callers, schemas, errors, retries, or downstream assumptions need definition.
6. Use Data & Storage Design Agent when persistence, indexing, metadata, retention, or privacy needs definition.
7. Use Configuration & Environment Contract Agent when settings, environment variables, or preflight checks need definition.
8. Use Test & Evaluation Strategy Agent when validation layers, mocks, datasets, or acceptance criteria need definition.
9. Use UX & Human Workflow Agent when users, reviewers, feedback, fallback, or human-in-the-loop states need definition.
10. Select the blueprint agent.
11. Start the planning companion.
12. Define the configuration contract.
13. Bring in Foundry integration.
14. Decide whether Microsoft Agent Framework makes sense.
15. Add authentication and local developer setup.
16. Add responsible AI and safety requirements.
17. Add security and compliance review.
18. Design monitoring and evaluation.
19. Prepare operations readiness.
20. Design the app flow.
21. Define input and output schemas.
22. Plan the minimal implementation.
23. Build the thin first version.
24. Validate with a manual test.
25. Add evaluation.
26. Prepare for deployment.

## 1. Pick The Application Scenario

Goal: state the app in plain language before choosing services or code structure.

Examples:

```text
I want to build an app that extracts metadata from product images for search.
```

```text
I want to build a RAG assistant over internal documents.
```

```text
I want to build a document processing app for invoices and receipts.
```

Start with this prompt in VS Code Chat:

```text
/design-ai-agent-solution Design an AI agent solution for [your scenario].
```

Expected output:

1. Application intent.
2. Recommended architecture, contract, or data design specialists.
3. Recommended configuration, test/evaluation, or UX workflow specialists.
4. Recommended blueprint agent.
5. Required Azure services.
6. Configuration needs.
7. Integration flow.
8. Safety and authentication notes.

Checkpoint: you can explain what the app does, who uses it, what input it accepts, and what output it returns.

## 1A. Start From A BRD Or PRD

Goal: convert product or business requirements into a requirement-to-agent implementation plan before writing code.

Use this path when you already have one of these inputs:

1. Business Requirements Document.
2. Product Requirements Document.
3. Feature brief.
4. Issue or epic description.
5. Pasted requirements summary.

Start with this prompt in VS Code Chat:

```text
/implement-from-brd-prd [paste requirements or provide a workspace file path]
```

Example:

```text
/implement-from-brd-prd docs/customer-support-assistant-prd.md
```

Expected output:

1. BRD/PRD source and evidence summary.
2. Verified requirements and assumptions.
3. Requirement-to-agent mapping.
4. Selected blueprints and why they fit.
5. Architecture, API, data, configuration, UX, and test/evaluation handoffs.
6. Security, safety, monitoring, and operations handoffs.
7. Microsoft Agent Framework fit assessment.
8. Phased implementation plan.
9. First bounded implementation step for Application Implementation Validation Agent.
10. Missing decisions and open questions.

Checkpoint: every implementation step traces back to a verified requirement, assumption, or open decision. If the BRD/PRD is incomplete, the plan should stop at missing inputs instead of inventing requirements or Azure resources.

## 1B. Start From Architecture Markdown Or A Diagram

Goal: convert an architecture artifact into a design handoff before writing code.

Use this path when you already have one of these inputs:

1. Markdown architecture notes.
2. Mermaid or PlantUML diagram text.
3. draw.io or Visio export text.
4. Architecture decision records.
5. Component, deployment, integration, or data-flow notes.
6. Pasted diagram description.

Start with this prompt in VS Code Chat:

```text
/design-from-architecture [paste Markdown architecture notes or provide a workspace file path]
```

Example:

```text
/design-from-architecture docs/customer-support-architecture.md
```

If pasting Markdown directly, put the architecture content after the slash command:

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

The Architecture To Design Intake in `browser/index.html` generates a longer prompt with guardrail instructions. That full prompt is valid and useful when you want the agent to explicitly separate verified facts, assumptions, unsupported inferences, and open decisions, and to avoid inventing components, Azure resources, endpoints, model deployments, security boundaries, test results, or implementation evidence.

Expected output:

1. Architecture source and evidence summary.
2. Verified architecture elements and assumptions.
3. Unsupported inferences and open decisions.
4. Architecture-to-agent mapping.
5. Selected blueprints and why they fit.
6. Architecture, API, data, configuration, UX, and test/evaluation handoffs.
7. Security, safety, monitoring, and operations handoffs.
8. Microsoft Agent Framework fit assessment.
9. Design plan and implementation handoff sequence.
10. First bounded design or implementation step.

Checkpoint: every design or implementation step traces back to a verified architecture element, assumption, or open decision. If the input is only an image and the agent cannot inspect image contents directly, provide Markdown notes, Mermaid or PlantUML text, OCR output, exported diagram text, or a user summary instead of expecting the agent to infer the diagram.

## 2. Select The Blueprint Agent

Goal: choose the narrowest useful application blueprint.

Use this prompt when you already know the target pattern:

```text
/design-ai-agent-solution Use the RAG Search App Agent to design a support assistant over product documentation.
```

For other scenarios, replace `RAG Search App Agent` with the relevant blueprint agent name.

Expected output:

1. Agent purpose.
2. Input and output contract.
3. Required Azure services.
4. Model or service choices.
5. Configuration fields.
6. Integration flow.
7. Safety and authentication notes.

Checkpoint: you know which agent owns the application design and which shared specialists need to review it.

## 3. Start The Planning Companion

Goal: keep the implementation organized once the design direction is selected.

Use this prompt after the application orchestrator or blueprint agent has produced a design:

```text
Application Planning Companion Agent, tag along with this app build. Track the current design, decisions, implementation steps, handoff agents, validation checks, and open questions.
```

Ask it to manage a specific step when you need coordination:

```text
Application Planning Companion Agent, manage the configuration-contract step and tell me which agent owns each decision.
```

Ask it to prepare a bounded step for implementation when you are ready for file changes or commands:

```text
Application Planning Companion Agent, prepare the README quickstart step for implementation and define the files, placeholders, validation command, and acceptance criteria.
```

Hand off to the implementation and validation agent when terminal execution or validation evidence is needed:

```text
Application Implementation Validation Agent, implement the README quickstart step from the current plan and run the focused validation check.
```

Expected output:

1. Current step.
2. Implementation tracker.
3. Recommended owner or handoff agent.
4. Action taken or next task list.
5. Validation check.
6. Open decisions.

Checkpoint: the app has a living implementation tracker before code or configuration work spreads across files.

## 4. Define The Configuration Contract

Goal: define the settings the app needs before writing implementation code.

Use this prompt:

```text
Design the configuration contract for this agent, including environment variables, model settings, service endpoints, and required secrets.
```

Common configuration fields:

```text
AZURE_AI_PROJECT_ENDPOINT=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT_NAME=
AZURE_AI_SEARCH_ENDPOINT=
AZURE_AI_SEARCH_INDEX=
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
```

For quickstarts, key-based authentication may appear. For production, prefer Microsoft Entra ID and managed identity where possible.

Checkpoint: every required endpoint, deployment name, index name, and credential source is named.

## 5. Bring In Foundry Integration

Goal: confirm how the app connects to Microsoft Foundry and model deployments.

Use this prompt:

```text
Use the Foundry Integration Agent to identify the Foundry project endpoint, model deployment name, quota considerations, and required app settings.
```

Confirm:

1. Foundry project endpoint.
2. Model deployment name.
3. Model family and version.
4. Region availability.
5. Quota or capacity risk.
6. Whether the endpoint is project-scoped or resource-scoped.

Checkpoint: you know which endpoint the app calls, which deployment name it uses, and whether quota is sufficient for testing.

## 6. Decide Whether Microsoft Agent Framework Makes Sense

Goal: choose whether the design should stay as a lightweight service integration or become a runnable Microsoft Agent Framework application.

Use this prompt after the blueprint, Foundry, and configuration needs are clear:

```text
Azure AI Application Orchestrator, assess whether Microsoft Agent Framework makes sense for this app. Explain the fit, non-fit reasons, handoff agent, expected scaffold shape, and validation checks.
```

Use Microsoft Agent Framework when the app needs one or more of these capabilities:

1. A runnable agent or workflow runtime rather than only design guidance.
2. Tool calling, actions, or multi-step orchestration with clear boundaries.
3. Stateful agent behavior, reusable workflows, or handoffs between app agents.
4. Microsoft Foundry-connected model deployments, tracing, debugging, evaluation, or deployment lifecycle.
5. A production path where implementation, validation, and operational evidence matter.

Keep the implementation simpler when the task is only a learning lab, catalog browsing, a one-off SDK call, static design documentation, or a prototype that does not need an agent runtime.

If Microsoft Agent Framework fits, use the planning companion to convert the decision into a bounded implementation step:

```text
Application Planning Companion Agent, add a Microsoft Agent Framework implementation option to the tracker, including scaffold boundaries, required configuration, validation command, and open decisions.
```

Then hand execution to the implementation and validation agent only after the step has files, placeholders, acceptance criteria, and a validation check:

```text
Application Implementation Validation Agent, implement the approved Microsoft Agent Framework scaffold step and run the focused validation check.
```

Checkpoint: the plan states either "use Microsoft Agent Framework" with a reason and validation path, or "do not use it yet" with a simpler implementation route.

## 7. Add Authentication And Local Developer Setup

Goal: design secure local and production authentication.

Use this prompt:

```text
Use the Auth Config Agent to design local and production authentication for this app using DefaultAzureCredential where possible.
```

Ask for:

1. Local `.env` variables.
2. Azure CLI login expectations.
3. Managed identity plan for production.
4. Required RBAC roles.
5. Secret handling rules.
6. Endpoint validation steps.

Recommended direction:

| Environment | Authentication approach |
| --- | --- |
| Local development | `az login` plus `DefaultAzureCredential` |
| Production | Managed identity |
| Secrets | Key Vault or app settings, never committed |
| Access | Least privilege RBAC |

Checkpoint: you can explain how local auth differs from production auth.

## 8. Add Responsible AI And Safety

Goal: define safety policy before implementation begins.

Use this prompt:

```text
Use the Responsible AI Safety Agent to define input validation, output filtering, moderation, refusal behavior, and logging requirements for this app.
```

Ask it to cover:

1. Unsafe input handling.
2. Prompt-injection risks.
3. Content filtering.
4. PII handling.
5. Generated-content disclosure.
6. Human review thresholds.
7. Audit logging.
8. Evaluation checks.

Checkpoint: the app has a documented safety policy before code is written.

## 9. Add Security And Compliance Review

Goal: identify security and compliance controls before implementation choices make them expensive to change.

Use this prompt:

```text
Use the Security & Compliance Agent to review this Azure AI app design for threat modeling, data protection, secrets, RBAC, network exposure, and compliance readiness.
```

Ask it to cover:

1. Data classification and retention.
2. User roles and least privilege.
3. Secret handling and credential flow.
4. Network exposure and service boundaries.
5. Audit, review, and compliance-sensitive gaps.
6. Required security validation before deployment.

Checkpoint: launch-blocking security controls and open compliance questions are visible before code is written.

## 10. Design Monitoring And Evaluation

Goal: define what the team must observe, measure, and evaluate once the app runs.

Use this prompt:

```text
Use the Monitoring & Evaluation Agent to define telemetry, tracing, metrics, alerts, evaluation checks, and production quality signals for this app.
```

Ask it to cover:

1. Runtime health signals.
2. AI quality signals such as grounding, relevance, extraction accuracy, or retrieval quality.
3. Safety and refusal monitoring.
4. Latency, failure, and cost signals.
5. Privacy-safe logging rules.
6. Dashboard and alert ownership.

Checkpoint: the app has observable success, failure, safety, and quality signals.

## 11. Prepare Operations Readiness

Goal: make the app supportable before deployment planning begins.

Use this prompt:

```text
Use the Operations Readiness Agent to define production readiness, runbook, rollback, incident response, support handoff, quota, and cost guardrail requirements for this app.
```

Ask it to cover:

1. Release checklist.
2. Runbook and support owner.
3. Rollback and recovery plan.
4. Quota, rate-limit, and dependency risks.
5. Incident response and escalation path.
6. Operational acceptance criteria.

Checkpoint: the app has a supportable launch path with owners, runbooks, and rollback expectations.

## 12. Design The App Flow

Goal: describe the request lifecycle from input to response.

For a RAG app, use:

```text
RAG Search App Agent, give me the end-to-end request flow from user query to final grounded answer.
```

Expected RAG flow:

```text
User query
-> validate input
-> create embedding if needed
-> retrieve documents from Azure AI Search
-> assemble grounded prompt
-> call model deployment
-> apply safety and output checks
-> return answer with citations
-> log telemetry
```

For a document processing app, use:

```text
Document Processing App Agent, give me the end-to-end request flow for extracting invoice fields.
```

Expected document flow:

```text
Upload document
-> validate file type and size
-> submit to Document Intelligence
-> extract fields
-> check confidence scores
-> route low-confidence fields to review
-> return normalized JSON
-> store result
```

For a vision app, use:

```text
Vision Chat App Agent, give me the end-to-end request flow for image-aware question answering.
```

Expected vision flow:

```text
Upload image and question
-> validate file type, size, and content policy
-> encode or attach image input
-> call the model or vision service
-> apply output safety checks
-> return answer or structured result
-> log telemetry
```

Checkpoint: every step between user input and app response is named.

## 13. Define Inputs And Outputs

Goal: make the app contract clear enough for frontend, backend, and tests.

Use this prompt:

```text
Define the input and output JSON schemas for this agent.
```

Example RAG input:

```json
{
  "query": "How do I reset my device?",
  "conversationId": "abc123",
  "filters": {
    "product": "Device A"
  }
}
```

Example RAG output:

```json
{
  "answer": "To reset Device A...",
  "citations": [
    {
      "title": "Device A Manual",
      "source": "device-a-manual.pdf",
      "chunkId": "manual-42"
    }
  ],
  "confidence": "high"
}
```

Example document processing output:

```json
{
  "documentType": "invoice",
  "fields": {
    "vendorName": "Contoso Ltd.",
    "invoiceNumber": "INV-1001",
    "invoiceDate": "2026-07-02",
    "total": 1234.56
  },
  "confidence": {
    "vendorName": 0.98,
    "invoiceNumber": 0.96,
    "invoiceDate": 0.94,
    "total": 0.99
  },
  "needsReview": false
}
```

Checkpoint: schemas are stable enough to build tests against them.

## 14. Plan The Minimal Implementation

Goal: turn the design into a small task list for a working prototype.

Use this prompt:

```text
Break this AI agent application design into implementation tasks for a minimal working version.
```

Suggested task list:

1. Create project structure.
2. Add configuration loader.
3. Add Azure client factory.
4. Add authentication setup.
5. Add agent service class.
6. Add API route or CLI entrypoint.
7. Add safety checks.
8. Add telemetry.
9. Add tests with mocked Azure responses.
10. Add README quickstart.

Checkpoint: the first version has one clear user-facing operation.

## 15. Build The Thin First Version

Goal: implement the smallest useful path before adding extra UI or workflow features.

For a RAG app:

```text
POST /ask
-> accepts query
-> retrieves top 3 documents
-> calls model
-> returns answer and citations
```

For a document app:

```text
POST /extract
-> accepts document
-> calls Document Intelligence
-> returns normalized fields
```

For a vision app:

```text
POST /analyze-image
-> accepts image
-> sends image to model or service
-> returns structured result
```

Avoid building dashboards, admin panels, multi-user workflows, or advanced review queues until the core agent path works.

Checkpoint: one end-to-end operation runs with mocked services or real configuration.

## 16. Validate With A Manual Test

Goal: prove the app path works with one known-good test case.

Example RAG test:

```text
Question: What is the return policy?
Expected: Answer cites the return-policy document.
```

Example document processing test:

```text
Input: sample invoice
Expected: vendor, invoice number, date, total, and line items extracted.
```

Example vision test:

```text
Input: product image
Expected: product type, visible attributes, tags, and confidence notes.
```

Checkpoint: one end-to-end request works and produces the expected output shape.

## 17. Add Evaluation

Goal: define how you will know the agent is good enough.

Use this prompt:

```text
Define evaluation checks for this agent application, including accuracy, safety, grounding, and failure behavior.
```

Useful checks:

1. Correct answer or extracted fields.
2. Citation presence for RAG.
3. No unsupported claims.
4. Safe refusal behavior.
5. Clean handling of missing configuration.
6. Clean handling of service timeout.
7. No secrets in logs.
8. Cost-aware request limits.

Checkpoint: evaluation covers both success behavior and failure behavior.

## 18. Prepare For Deployment

Goal: verify configuration, auth, quota, and safety before deploying.

Use these prompts:

```text
Foundry Integration Agent: verify deployment endpoint and model settings.
```

```text
Auth Config Agent: verify production managed identity and RBAC.
```

```text
Responsible AI Safety Agent: verify safety and logging requirements before deployment.
```

```text
Security & Compliance Agent: verify launch-blocking security and compliance readiness gaps.
```

```text
Monitoring & Evaluation Agent: verify telemetry, alerting, tracing, and evaluation signals.
```

```text
Operations Readiness Agent: verify runbook, rollback, support handoff, incident response, quota, and cost guardrails.
```

Deployment checklist:

1. Environment variables documented.
2. Secrets not committed.
3. Managed identity configured.
4. RBAC roles assigned.
5. Model quota checked.
6. Retry and timeout behavior configured.
7. Telemetry enabled.
8. Cleanup plan documented.
9. Security and compliance gaps reviewed.
10. Monitoring and evaluation signals documented.
11. Runbook, rollback, and support handoff prepared.

Checkpoint: the app is ready for Azure deployment planning.

## Suggested First Application

Start with a minimal RAG Search App Agent prototype. It exercises the most reusable application patterns: configuration, auth, retrieval, model calls, grounding, citations, safety, and evaluation.

Use this prompt:

```text
/design-ai-agent-solution Design a minimal RAG Search App Agent for answering questions over local product documentation, including config contract, request flow, safety checks, and implementation tasks.
```

Then continue with:

```text
Use the Auth Config Agent to design local and production authentication for this RAG app.
```

Then:

```text
Use the Responsible AI Safety Agent to define safety checks and evaluation criteria for this RAG app.
```

Recommended implementation path:

```text
Design -> Planning Companion -> Config -> Auth -> Safety -> Implementation Validation -> Test -> Evaluate -> Deploy
```
