# Casewright — Architecture

> Draw.io MCP tools were not available during generation, so the architecture is rendered
> here in Mermaid (degraded Mode B). A `.drawio` can be regenerated later by re-running
> Phase 1 with the Draw.io MCP server connected.

## Component Inventory

| Component | Azure Service | Identity | Responsibility |
|-----------|---------------|----------|----------------|
| `casewright-api` | Container Apps | User-assigned MI | FastAPI: chat, pipeline, sharepoint, health |
| `casewright-worker` | Container Apps | User-assigned MI | Service Bus consumer → SharePoint sync → conditional indexer run |
| `casewright-scheduler` | Functions (Flex) | User-assigned MI | Timer + HTTP triggers → enqueue sync requests |
| Search | Azure AI Search | System MI | Vector + semantic index, skillsets, indexers |
| OpenAI | Azure OpenAI | — | Chat + embedding deployments |
| Blob | Storage Account | — | Ingestion landing zone + knowledge store |
| Cosmos | Cosmos DB (NoSQL) | — | Chat history (hierarchical PK) + sync state |
| Queue | Service Bus | — | Durable sync-request queue |
| Vault | Key Vault | — | Non-MI secrets (e.g. Graph app secret) |
| Insights | Application Insights | — | Telemetry |
| Foundry (optional) | Azure AI Foundry | — | Hosted prompt-agent runtime |

## System Diagram

```mermaid
flowchart TB
    subgraph Clients
        Web[Web Chat Client]
        Teams[Teams / M365 Bot]
    end

    subgraph ContainerApps[Azure Container Apps]
        API[casewright-api\nFastAPI]
        Worker[casewright-worker\nSB consumer]
    end

    Sched[casewright-scheduler\nFunctions: Timer + HTTP]

    subgraph Data
        Search[(Azure AI Search\nvector + semantic)]
        Blob[(Blob Storage)]
        Cosmos[(Cosmos DB\nhistory + sync-state)]
        SB[[Service Bus queue]]
    end

    OpenAI[[Azure OpenAI\nchat + embeddings]]
    Graph[(Microsoft Graph\nSharePoint)]
    Foundry[[Foundry prompt-agent\noptional]]

    Web -->|/api/chat| API
    Teams -->|/api/chat| API
    API -->|hybrid query + rerank| Search
    API -->|grounded answer| Foundry
    API -->|fallback| OpenAI
    API -->|history| Cosmos
    API -->|enqueue sync| SB
    Sched -->|timer/http enqueue| SB
    SB --> Worker
    Worker -->|delta detect| Graph
    Worker -->|upload changed| Blob
    Worker -->|sync state| Cosmos
    Worker -->|run if changes>0| Search
    Search -->|pull + skillset| Blob
    Search -->|embeddings| OpenAI
```

## Data Flow — Ingestion

```mermaid
sequenceDiagram
    participant Sched as Scheduler (timer)
    participant SB as Service Bus
    participant Worker
    participant Graph as MS Graph
    participant Blob
    participant Cosmos
    participant Search

    Sched->>SB: enqueue {tenantId, siteId}
    SB->>Worker: sync message
    Worker->>Graph: list drive items
    Worker->>Cosmos: read last sync state
    Worker->>Worker: classify added/updated/unchanged/deleted
    alt changes > 0
        Worker->>Blob: upload added+updated, tombstone deleted
        Worker->>Cosmos: persist new high-water-marks
        Worker->>Search: run indexer (multimodal/markdown/json)
        Search->>Blob: pull + skillset (extract/chunk/embed)
    else no changes
        Worker-->>Worker: skip indexer run
    end
```
