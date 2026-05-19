# Business Requirements Document
# Dynamic Agent Orchestration Platform (DAOP)

## 1. Project Overview

**Project Name:** Dynamic Agent Orchestration Platform (DAOP)
**Version:** 1.0
**Date:** 2026-04-24
**Status:** Draft

### 1.1 Executive Summary

DAOP is a standalone agentic environment built on Microsoft Agent Framework (MAF) and Azure AI Foundry that dynamically creates, configures, and manages AI agents based on user intent and project requirements — at both development and operational time. It is an independent platform that can optionally integrate with Azure Architecture Factory (AAF) as a callable tool for architecture generation and project scaffolding.

---

## 2. Business Objectives

- Enable a single entry point where a user can describe a goal and receive a fully assembled team of purpose-built AI agents
- Support dynamic agent creation: agents are not pre-deployed for every scenario but are instantiated on demand from a managed catalog of templates
- Cover both development-time tasks (architecture design, code generation, scaffolding, IaC) and operational-time tasks (monitoring, incident response, cost optimization, deployment)
- Integrate AAF as an optional development tool for architecture diagram generation and project scaffolding
- Be fully deployable to Azure with production-grade security (Managed Identity, Key Vault, RBAC, private networking)

---

## 3. Scope

### In Scope
- Meta-orchestrator agent: receives natural-language goals and decomposes them into agent tasks
- Agent factory service: instantiates sub-agents from templates at runtime using MAF SDK
- Agent registry: Cosmos DB-backed catalog of agent templates, capabilities, and configuration
- Core agent templates: Architect, Developer, DevOps/Ops, Analyst, Security
- AAF integration tool: HTTP adapter calling AAF's BRD intake and architecture generation APIs
- Azure deployment infrastructure: Container Apps, Foundry Standard Setup, Cosmos DB, Service Bus, ACR
- Observability: Application Insights traces per agent, structured logging, eval dataset harvesting

### Out of Scope
- Modification of AAF internals
- General-purpose chatbot interface (focus is on agentic task execution, not conversational UI)
- On-premises deployment

---

## 4. Functional Requirements

### FR-01: Intent Reception and Decomposition
The orchestrator agent shall accept a natural-language project goal or task description and decompose it into a prioritized plan of sub-tasks, each mapped to an agent type.

### FR-02: Dynamic Agent Selection
Given a decomposed task plan, the orchestrator shall query the agent registry to select the best-fit agent template for each task, considering: required capabilities, available tools, and cost tier.

### FR-03: Dynamic Agent Instantiation
The platform shall instantiate agents on demand using the MAF SDK (`client.agents.create_version`) or by routing via `ConnectedAgent` to pre-deployed agent endpoints registered in the catalog.

### FR-04: Agent Lifecycle Management
The platform shall track active agent sessions per project context. Idle agents shall be suspended after a configurable TTL. State shall be persisted in Cosmos DB.

### FR-05: Agent Registry and Catalog
A Cosmos DB collection shall store agent template definitions including: name, description, capabilities list, required tools, model preferences, system prompt template, and deployment endpoint (when pre-deployed).

### FR-06: AAF Integration Tool
A tool callable by the Architect agent shall POST a BRD payload to the AAF intake API and poll for architecture diagram and Bicep scaffold output, returning results to the orchestrator context.

### FR-07: Multi-Agent Coordination
Agents shall be able to hand off results and context to other agents via the orchestrator. Shared project context shall be maintained in Cosmos DB and passed through agent thread state.

### FR-08: Human-in-the-Loop (HITL)
The orchestrator shall support pause-and-confirm steps where users approve agent plans before execution proceeds (e.g., before infrastructure deployment or code commits).

### FR-09: Observability and Tracing
Every agent invocation shall emit structured traces to Application Insights. Traces shall include: agent name, template version, task, duration, token usage, and outcome.

### FR-10: Secure Configuration
All secrets (API keys, connection strings) shall be stored in Azure Key Vault. Agents shall authenticate using Managed Identity. No secrets in source code or environment files in production.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Scalability** | Orchestrator scales to 10 concurrent project sessions minimum |
| **Latency** | Orchestrator decomposition < 5s; agent instantiation < 15s |
| **Availability** | 99.5% uptime for orchestrator; sub-agents tolerate cold start |
| **Security** | Zero standing secrets; Managed Identity everywhere; private endpoints for Cosmos DB and Key Vault in production |
| **Deployability** | Full `azd up` from zero in < 20 minutes to dev environment |
| **Observability** | 100% of agent calls traced; retention 30 days in Log Analytics |
| **Extensibility** | New agent templates addable by writing a template definition + registering in catalog — no platform code changes |

---

## 6. Technical Architecture

### 6.1 Components

| Component | Technology | Role |
|---|---|---|
| Meta-Orchestrator | MAF Python, Foundry hosted agent | Entry point; decomposes intent; manages agent lifecycle |
| Agent Factory | MAF SDK + Python service | Creates/connects agent instances at runtime |
| Agent Registry | Azure Cosmos DB | Catalog of templates, active sessions, project context |
| Agent Templates | MAF Python (per type) | Architect, Developer, Ops, Analyst, Security |
| AAF Tool Adapter | Python HTTP client | Calls AAF intake API; returns architecture artifacts |
| Async Task Bus | Azure Service Bus | Decouples long-running agent tasks from synchronous calls |
| Secrets Store | Azure Key Vault | All credentials and connection strings |
| Observability | Application Insights + Log Analytics | Traces, metrics, dashboards |
| Container Runtime | Azure Container Apps | Scalable, serverless container hosting per agent |
| Model Backend | Azure AI Foundry (Standard Setup) | GPT-4o + embeddings for all agents |

### 6.2 Deployment Model

- Orchestrator: Always-on Container App (min replicas: 1)
- Sub-agent containers: Scale-to-zero Container Apps, triggered via HTTP or Service Bus
- Infrastructure: Bicep with azd, parameterized for dev/staging/prod

### 6.3 Integration Points

- **AAF API**: `POST /api/brd-intake` → poll `GET /api/projects/{id}/status`
- **GitHub Copilot**: Developer agent may use Copilot APIs for code generation tasks
- **Azure DevOps / GitHub Actions**: Ops agent can trigger pipelines via REST API tools

---

## 7. Agent Template Catalog (Initial Set)

| Template | Capabilities | Key Tools |
|---|---|---|
| `architect` | Architecture design, diagram generation, IaC scaffolding | AAF tool, draw.io MCP, Bicep generator |
| `developer` | Code generation, refactoring, test writing | Copilot API, GitHub API, file tools |
| `ops` | Deployment, monitoring, incident triage | Azure CLI tools, Container Apps API, App Insights |
| `analyst` | Requirements analysis, cost estimation, traceability | Azure Cost API, AAF intake, doc tools |
| `security` | CVE scanning, RBAC audit, policy compliance | azqr tool, Key Vault API, Defender API |

---

## 8. Implementation Language and Preferences

- **Primary language:** Python
- **Framework:** Microsoft Agent Framework (MAF)
- **IaC:** Bicep (primary), azd for deployment
- **Deployment target:** Azure Container Apps (Foundry Standard Setup)
- **Authentication:** DefaultAzureCredential / Managed Identity

---

## 9. Constraints

- Must remain independent of AAF codebase; AAF is consumed only via HTTP API
- Must use MAF SDK (not raw OpenAI API) for all agent logic
- All agent templates must be runnable locally with `.env` configuration for developer inner loop
- Must support `azd up` as the single deploy command

---

## 10. Success Criteria

- A user can describe a software project goal and receive a working architecture diagram, code scaffold, and Bicep infra generated by a dynamically assembled agent team
- New agent templates can be added in < 1 hour by a developer without modifying orchestrator code
- Full platform deploys from zero to running in Azure in < 20 minutes via `azd up`
- All agent calls are traceable end-to-end in Application Insights
