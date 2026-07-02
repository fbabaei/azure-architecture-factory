---
name: "Design AI Agent Solution"
description: "Select and configure reusable Azure AI application agents for a real application design, including BRD/PRD intake, architecture artifact intake, API/data contracts, configuration, UX workflow, testing, evaluation, safety, auth, security, monitoring, operations, and validation."
agent: "Azure AI Application Orchestrator"
tools: [read, search, agent]
argument-hint: "Describe the application, users, inputs, outputs, and desired AI capabilities."
---
Design an application-agent solution for the described scenario.

Focus on application mode. Use the registry and catalog to select reusable blueprint agents.
If the user provides a BRD, PRD, feature brief, requirements file path, or pasted requirements, extract verified requirements first and map them to the Foundry agents before proposing implementation steps.
If the user provides Markdown architecture notes, Mermaid or PlantUML text, a diagram export, an ADR, component notes, or pasted architecture details, extract verified architecture elements first and map them to the Foundry agents before proposing design or implementation steps.

Return:
- selected agent blueprints
- BRD/PRD requirement summary and requirement-to-agent mapping when requirements are supplied
- architecture artifact summary and architecture-to-agent mapping when architecture input is supplied
- architecture, API integration contract, and data storage handoffs when the app is new or underspecified
- configuration/environment, test/evaluation, and UX/human workflow handoffs when the app is ready to move toward implementation
- configuration contract
- input and output contracts
- integration pattern
- Microsoft Agent Framework fit assessment when a runnable agent runtime, tools, stateful workflow, Foundry lifecycle, evaluation, or deployment path may be useful
- safety and auth considerations
- security, monitoring, and operations readiness considerations when production-facing
- validation checks
- recommended implementation order
