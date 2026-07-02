---
name: "Implement From BRD Or PRD"
description: "Convert a Business Requirements Document (BRD), Product Requirements Document (PRD), feature brief, or requirements file into an Azure AI Agent Foundry implementation plan using the application orchestrator, design specialists, blueprints, shared platform agents, and implementation validation handoff."
agent: "Azure AI Application Orchestrator"
tools: [read, search, agent]
argument-hint: "Provide a BRD/PRD file path, pasted requirements, or a concise product brief plus target users, constraints, and desired Azure AI capabilities."
---
Use Azure AI Agent Foundry agents to convert the supplied BRD, PRD, feature brief, or requirements artifact into an implementation-ready application plan.

Treat the document as input evidence, not as complete truth. Extract only what is present, label assumptions, and ask for missing decisions when implementation would otherwise require invention.

Process:
1. Identify the source of requirements: file path, pasted content, or summarized brief.
2. Extract verified product goals, user roles, workflows, functional requirements, nonfunctional requirements, data inputs, outputs, integrations, constraints, risks, and acceptance criteria.
3. Map each requirement to the relevant Foundry agents:
   - Azure AI Application Orchestrator for overall routing.
   - Architecture & Design Agent for components, boundaries, flows, and design decisions.
   - API & Integration Contract Agent for APIs, tool contracts, events, schemas, errors, retries, and downstream assumptions.
   - Data & Storage Design Agent for data, storage, indexing, retention, metadata, embeddings, generated assets, audit, and privacy.
   - Configuration & Environment Contract Agent for environments, settings, secrets references, endpoint placeholders, and preflight checks.
   - Test & Evaluation Strategy Agent for deterministic tests, AI quality evaluation, mocks, datasets, and acceptance criteria.
   - UX & Human Workflow Agent for user journeys, review queues, fallbacks, confidence handling, and feedback loops.
   - Application Planning Companion Agent for tracking decisions and converting the plan into bounded steps.
   - Application Implementation Validation Agent for execution, command running, tests, local server checks, and validation evidence.
4. Select application blueprint agents only when the requirements support them.
5. Add Foundry integration, auth/config, Responsible AI, security/compliance, monitoring/evaluation, and operations readiness handoffs when the requirements imply production use or sensitive data.
6. Assess whether Microsoft Agent Framework fits the implementation based on runtime, tools/actions, state, workflow, tracing, evaluation, deployment, or Foundry lifecycle needs.
7. Produce a phased implementation plan with requirement traceability and validation gates.

Return:
- BRD/PRD source and evidence summary
- verified requirements and assumptions
- requirement-to-agent mapping
- selected blueprints and why
- architecture/API/data/configuration/UX/test handoffs
- security, safety, monitoring, and operations handoffs
- Microsoft Agent Framework fit assessment
- phased implementation plan
- bounded first implementation step for Application Implementation Validation Agent
- validation checks and acceptance criteria
- missing decisions and open questions

Do not invent requirements, Azure resources, endpoints, model deployments, file paths, test results, command output, user research, compliance findings, or implementation evidence. If the BRD/PRD is unavailable or incomplete, say what is missing and provide the safest next step.
