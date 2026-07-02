---
name: "Find AI Agent"
description: "Search Azure AI Agent Foundry by task intent, Azure service, app scenario, learning goal, keyword, or capability and recommend the best agent."
agent: "Azure AI Agent Foundry Orchestrator"
tools: [read, search, agent]
argument-hint: "Describe what you need an AI agent to do."
---
Find the best Azure AI Agent Foundry agent for this request.

Use `.github/agent-zone/ai-agent-index.json` and `.github/agent-zone/catalog.md`.

Return:
- recommended agent or agents
- mode: learning, application, or mixed
- why the agent fits
- required configuration or source references
- next action
