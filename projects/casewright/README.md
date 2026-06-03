# Casewright

Casewright is an agentic knowledge assistant that answers case and policy questions over
content sourced from SharePoint. It combines an Azure AI Foundry agent, hybrid + semantic
retrieval on Azure AI Search, and an event-driven ingestion pipeline that keeps the search
index in sync with SharePoint document libraries.

## Capabilities

- **Grounded chat** — a hosted `case-knowledge-agent` answers questions with citations. At
  query time it retrieves through a **Foundry IQ knowledge base** (`casewright-kb`) layered
  over the `casewright-index` and invoked as an MCP tool; when Foundry is not configured the
  service falls back to an in-process hybrid (vector + keyword) + semantic query over the same
  index (see [ADR-10](docs/architecture-decisions.md)).
- **SharePoint ingestion** — incremental delta sync detects added/updated/deleted documents
  via Microsoft Graph and only triggers indexers when there are net changes.
- **Event-driven worker** — a Service Bus queue (`sharepoint-sync`) decouples sync requests
  from processing; the worker runs delta sync and conditionally runs Search indexers.
- **Scheduled sync** — a Function App (`casewright-scheduler`) enqueues periodic sync jobs on
  a configurable cron schedule.
- **Conversation history** — chat turns are persisted in Cosmos DB with a hierarchical
  partition key (`/tenantId`, `/userId`, `/conversationId`) and TTL support.
- **Resilient processing** — the Service Bus queue uses a configurable `maxDeliveryCount`
  and lock duration; the worker dead-letters poison (unparseable) messages immediately and
  abandons transient failures for retry until the delivery limit is reached.
- **Built-in chat UI** — a dependency-free static chat client is served from the API at `/`
  for quick manual testing of grounded answers and citations.
- **Observability** — optional Azure Monitor / OpenTelemetry instrumentation emits traces and
  custom metrics (sync runs, net changes, indexer runs, dead-lettered messages) when an
  Application Insights connection string is present.

## Architecture

| Component | Hosting | Purpose |
| --- | --- | --- |
| `casewright-api` | Azure Container Apps (external ingress, port 8000) | FastAPI chat + pipeline + SharePoint control endpoints; serves the static chat UI at `/` |
| `casewright-worker` | Azure Container Apps (internal) | Service Bus consumer running delta sync + indexer triggering |
| `casewright-scheduler` | Azure Functions (Flex Consumption) | Timer-triggered enqueue of sync jobs |
| Azure AI Search | `casewright-index` + `casewright-semantic` | Index of record; backs the Foundry IQ KB and the offline hybrid query |
| Foundry IQ knowledge base | `casewright-kb` (MCP server over `casewright-index`) | Primary query-time retrieval + reranking, invoked by the agent via the `casewright-kb-mcp` connection |
| Azure AI Foundry | `case-knowledge-agent` | Hosted agent orchestration; owns retrieval through the KB MCP tool |
| Azure OpenAI | `gpt-4o`, `text-embedding-3-large` | Chat completions and embeddings (3072 dims) |
| Cosmos DB | `casewright` (`chat-history`, `sync-state`) | Conversation history and sync watermarks |
| Service Bus | `sharepoint-sync` queue | Decoupled sync dispatch with dead-letter + retry |
| Storage | `ingestion`, `knowledge-store` | Source documents and enriched knowledge store |
| Application Insights | via `APPLICATIONINSIGHTS_CONNECTION_STRING` | Optional traces + custom sync/indexer/dead-letter metrics |

See [docs/architecture-decisions.md](docs/architecture-decisions.md) for the ADRs and
[diagrams/casewright.md](diagrams/casewright.md) for the system diagram.

## Project layout

```
casewright/
├── project-manifest.json     # Machine-readable project descriptor
├── pyproject.toml            # Package + test configuration (src layout)
├── src/
│   ├── Dockerfile            # API / worker container image
│   ├── requirements.txt      # Runtime dependencies for container builds
│   └── casewright/           # Python package
│       ├── agents/           # Foundry agent + prompts
│       ├── api/              # FastAPI app + routers
│       ├── core/             # Settings, lazy Azure clients, models
│       ├── functions/        # Scheduler Function App
│       ├── ingestion/        # Search index, datasource, skillsets, pipeline
│       ├── repositories/     # Cosmos-backed history + sync state
│       ├── retrieval/        # Hybrid + semantic query
│       ├── sharepoint/       # Graph client + delta sync + dispatcher
│       ├── web/              # Static chat UI (served from the API)
│       └── worker/           # Service Bus worker (dead-letter + retry)
│       # core/observability.py — optional Azure Monitor / OTel instrumentation
├── azure.yaml                # azd service map for `azd up`
├── infra/                    # Bicep IaC (main + modules + params)
├── tests/                    # Pytest suite
└── docs/                     # Requirements, ADRs, retrieval + security design
```

## Local development

```pwsh
# From projects/casewright
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Run tests
pytest -q

# Run the API locally (clients are lazy; Azure connectivity only needed at call time)
uvicorn casewright.api.main:app --reload --port 8000
# The static chat UI is then available at http://localhost:8000/
```

The test suite covers unit logic (delta sync, models, worker gating), worker dead-letter /
retry handling, and end-to-end API flows (`tests/test_integration.py`) using a `TestClient`
with faked Azure collaborators — no Azure connectivity required.

Configuration is provided through environment variables consumed by
[`core/settings.py`](src/casewright/core/settings.py); see [.env.example](.env.example) for the
full surface. All settings have safe defaults so the app imports without any Azure
connectivity; production endpoints are injected by the deployment.

## Deployment

See [DEPLOY.md](DEPLOY.md) for full instructions. The fastest path is the Azure Developer
CLI, which uses [azure.yaml](azure.yaml) to build and deploy all three services:

```pwsh
azd up
```

Or deploy the infrastructure directly with Bicep:

```pwsh
az group create -n rg-casewright-dev -l eastus2
az deployment group create `
  -g rg-casewright-dev `
  -f infra/main.bicep `
  -p infra/params/dev.bicepparam
```

After the index exists, provision the Foundry IQ knowledge base and hosted agent (one-shot):

```pwsh
python scripts/deploy_agent.py deploy
```

This creates the `casewright-kb` knowledge base, the `casewright-kb-mcp` RemoteTool
connection, and the hosted `case-knowledge-agent`, then prints the agent id to set as
`FOUNDRY_AGENT_ID`. See [DEPLOY.md](DEPLOY.md) step 7 for details.

## Security model

Casewright is managed-identity-first: it uses `DefaultAzureCredential` everywhere and
provisions three user-assigned identities (api / worker / scheduler) for least-privilege
access. Local authentication is disabled on Search, Service Bus, OpenAI, and Cosmos, and
shared-key access is disabled on Storage. All role assignments are defined in
[infra/modules/rbac.bicep](infra/modules/rbac.bicep) and audited in
[docs/security/security-audit.json](docs/security/security-audit.json).
