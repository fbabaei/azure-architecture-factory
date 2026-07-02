---
name: "Learn AI Capability"
description: "Start a guided Azure AI learning route using the source repositories for AI services, vision, NLP, AI Search, Document Intelligence, Azure OpenAI, and Foundry labs."
agent: "Azure AI Learning Orchestrator"
tools: [read, search, agent]
argument-hint: "Describe the Azure AI capability, module, or lab you want to learn."
---
Create a guided learning route for the requested Azure AI capability.

Use the source repositories under `external/` and route to the relevant capability orchestrator.

Return:
- matched learning area
- source path or module reference
- prerequisites
- suggested learning sequence
- hands-on lab or application follow-up
- cleanup or cost reminders when Azure resources are involved
