# Architecture Notes — Dynamic Agent Orchestration Platform (DAOP)

## Component Inventory

### Compute — Azure Container Apps

| Component | Container App Name | Min Replicas | Scale Rule |
|---|---|---|---|
| Meta-Orchestrator | `daop-orchestrator` | 1 | HTTP (10 concurrent) |
| Agent Factory | `daop-agent-factory` | 0 | HTTP trigger |
| Agent Registry API | `daop-agent-registry` | 1 | HTTP (5 concurrent) |
| Architect Agent | `daop-agent-architect` | 0 | Service Bus + HTTP |
| Developer Agent | `daop-agent-developer` | 0 | Service Bus + HTTP |
| Ops Agent | `daop-agent-ops` | 0 | Service Bus + HTTP |
| Analyst Agent | `daop-agent-analyst` | 0 | Service Bus + HTTP |
| Security Agent | `daop-agent-security` | 0 | Service Bus + HTTP |

### Data — Azure Cosmos DB (NoSQL API)

| Collection | Partition Key | Purpose |
|---|---|---|
| `agent_templates` | `/template_id` | Catalog of reusable agent template definitions |
| `agent_sessions` | `/project_id` | Active session state per project context |
| `project_contexts` | `/project_id` | Shared project context across agent handoffs |
| `eval_traces` | `/agent_name` | Harvested traces for Foundry eval datasets |

### Messaging — Azure Service Bus

| Queue / Topic | Purpose |
|---|---|
| `daop-tasks` (queue) | Async task dispatch from orchestrator to sub-agents |
| `daop-results` (queue) | Result callbacks from sub-agents to orchestrator |
| `daop-hitl` (queue) | Human-in-the-loop approval requests |

### Security & Identity

| Resource | Role |
|---|---|
| Azure Key Vault | Secrets: Cosmos DB connection string, Service Bus namespace key, AAF API key, App Insights connection string |
| User-Assigned Managed Identity | `daop-identity` — assigned to all Container Apps |
| Azure AI Developer role | Granted to `daop-identity` on the Foundry project |
| Key Vault Secrets User role | Granted to `daop-identity` on the Key Vault |
| Cosmos DB Built-in Data Contributor | Granted to `daop-identity` on the Cosmos DB account |

### Observability

| Resource | Purpose |
|---|---|
| Log Analytics Workspace | Centralized log aggregation, 30-day retention |
| Application Insights | Agent trace telemetry, per-agent custom events |

### AI / Model Backend

| Resource | Purpose |
|---|---|
| Azure AI Foundry (Standard Setup) | Hub + Project for GPT-4o and embeddings model deployments |
| GPT-4o deployment (`gpt-4o`) | All agents — reasoning, code, analysis |
| text-embedding-3-small deployment | Semantic registry lookup for agent template matching |

---

## Primary Data Flow

```
User → POST /orchestrate
  → Meta-Orchestrator (decompose intent → task plan)
    → Agent Registry (select best-fit templates per task)
      → Agent Factory (instantiate/connect agents via MAF SDK)
        → Sub-agents (parallel execution via Service Bus tasks)
          → Results returned to Orchestrator thread state
            → Orchestrator assembles final response → User

Architect agent → AAF Tool Adapter → POST AAF /api/brd-intake
  → poll GET /api/projects/{id}/status → return drawio + Bicep artifacts
```

---

## Architecture Decisions

1. **Agent isolation via Container Apps**: each agent template runs in its own Container App to enable independent scaling, blue/green revisions, and fault isolation.
2. **Service Bus for async decoupling**: long-running agent tasks (code gen, IaC generation, security scans) are dispatched via Service Bus to avoid HTTP timeouts.
3. **Cosmos DB for shared context**: project context is stored in Cosmos DB so all agents in a session share the same state without coupling via in-memory structures.
4. **MAF SDK with deterministic fallback**: all agents adopt the Agent Framework Runtime Pattern — SDK runtime preferred, deterministic Python fallback always available.
5. **AAF consumed as HTTP API only**: no code-level dependency on AAF; the Architect agent calls AAF via the `AAFToolAdapter` HTTP client, preserving platform independence.
6. **Single managed identity**: one user-assigned identity (`daop-identity`) is shared across all Container Apps, simplifying RBAC management.
