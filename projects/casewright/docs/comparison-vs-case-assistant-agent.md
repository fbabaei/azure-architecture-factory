# Casewright vs. Case Assistant Agent

This document compares **Casewright** with the project it was modeled after,
**case-assistant-agent**. Both deliver the same product capabilities — grounded case Q&A
with citations, SharePoint ingestion, and conversation history — but differ substantially in
architecture, code structure, security model, and operations.

Casewright is a clean-room, independent rebuild. It shares no code with case-assistant-agent.

## Summary of differences

| Area | case-assistant-agent | casewright |
| --- | --- | --- |
| Python package | `case_assistant` under `backend/app/` | `casewright` under `src/casewright/` (src layout) |
| Architecture | Foundry-centric, coupled services + workflows | Event-driven, three-service split |
| Services | Single backend app | `casewright-api` (Container App), `casewright-worker` (Container App), `casewright-scheduler` (Function App) |
| Messaging | None (inline/coupled processing) | Service Bus `sharepoint-sync` queue (decoupled) |
| Search index | (its own) | `casewright-index` + `casewright-semantic` |
| Query-time retrieval | Foundry IQ knowledge base via hosted-agent MCP tool | Foundry IQ knowledge base (`casewright-kb`) via hosted-agent MCP tool; in-process hybrid query as offline fallback |
| Agent | (its own) | `case-knowledge-agent` |
| Cosmos DB | (its own) | `casewright` (`chat-history`, `sync-state`) |
| IaC | `main.bicep` + `main.parameters.json` (single env) | `main.bicep` + 14 modules + `dev`/`test`/`prod` bicepparam |
| RBAC | Out-of-band post-provision scripts | In-template `infra/modules/rbac.bicep` (8 role assignments) |
| Identities | Single / broader identity | Three user-assigned identities (api/worker/scheduler) |
| Clients | Eager construction at import | Lazy (`@lru_cache`), import with zero Azure connectivity |
| Tests | — | Pytest suite (9 passing), no Azure connectivity required |
| Packaging | `backend/` requirements | `pyproject.toml` (src layout) + shared `src/Dockerfile` |

## Advantages of Casewright

### 1. Least-privilege security
- **Three separate user-assigned identities** (api/worker/scheduler) instead of a shared or
  broader identity, so each service holds only the narrowly scoped role assignments it needs.
- **No account keys**: local authentication disabled on Search, Service Bus, OpenAI, and
  Cosmos; shared-key access disabled on Storage. This materially reduces the
  credential-leak surface. (The single exception is the Log Analytics shared key required for
  Container Apps log configuration.)

### 2. RBAC as infrastructure-as-code
- case-assistant-agent applies RBAC via **out-of-band post-provision scripts**
  (`setup_rbac.py`, `setup_cosmos_rbac.py`, `azd-postprovision-rbac.ps1/.sh`), which can
  drift, be skipped, or fail silently outside the deployment.
- casewright defines all role assignments **in `rbac.bicep`** — versioned, idempotent,
  reviewable in `what-if`, and deployed atomically with the resources they grant access to.

### 3. Scalability and resilience (event-driven decoupling)
- The **Service Bus `sharepoint-sync` queue** decouples sync requests from processing. The
  worker scales independently of the API, absorbs bursts, and retries failed messages instead
  of processing inline.
- Sync, indexing, and chat run as **three independently scalable services** rather than one
  coupled unit.

### 4. Cost and operational efficiency
- The scheduler runs on **Flex Consumption Functions** (scale-to-zero), so periodic sync does
  not require an always-on host.
- Indexers are triggered **only on net SharePoint changes**, avoiding wasteful indexer runs
  and the associated Search/OpenAI embedding costs when nothing changed.

### 5. Multi-environment readiness
- **Three bicepparam files** (`dev`/`test`/`prod`) versus a single `main.parameters.json`,
  giving clean per-environment promotion out of the box.

### 6. Cleaner, more testable codebase
- Modern **`src/` layout** with lazy (`@lru_cache`) Azure clients means the app imports and
  the test suite runs with **zero Azure connectivity** — a passing 9-test suite ships with the
  project.
- **14 focused Bicep modules** versus a more monolithic template — easier to reason about,
  review, and reuse.

### 7. Foundry IQ retrieval with a guaranteed local fallback (adopted parity)
- Casewright adopts case-assistant-agent's **Foundry IQ knowledge base** retrieval: a
  `casewright-kb` knowledge base over `casewright-index` is exposed as an MCP server, and the
  hosted `case-knowledge-agent` retrieves through it via a `casewright-kb-mcp` RemoteTool
  connection (ProjectManagedIdentity auth). Retrieval/reranking/reasoning effort are owned by
  the KB, so changes are configuration rather than redeploys (see ADR-10).
- Unlike the upstream project, casewright keeps its **in-process hybrid+semantic query as an
  offline fallback** (`retrieval/query.py`), so the service still answers locally when Foundry
  is not configured (ADR-2). Provisioning is one-shot via `scripts/deploy_agent.py`.

## Trade-offs

To be balanced, Casewright's advantages come with some costs:

- **More moving parts** (a queue plus three services) means slightly higher baseline
  complexity and more components to monitor.
- It introduces a **Service Bus dependency** that case-assistant-agent does not require.

## Conclusion

Casewright trades a modest increase in architectural complexity for materially better
**security posture, scalability, cost control, and deployability**, while preserving the full
feature set of case-assistant-agent.
