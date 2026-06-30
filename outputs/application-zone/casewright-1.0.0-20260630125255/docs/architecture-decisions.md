# Casewright — Architecture Decisions

This document records the design decisions made by the factory during generation.

## ADR-1 — Workload archetype: `rag-qa`
The BRD describes a knowledge base, grounded answers, document search, citations, and
semantic search. The factory classifier selects the **rag-qa** archetype, which drives a
retrieval subsystem (`knowledge-retrieval-architect`, Phase 2r) plus a chat service.

## ADR-2 — Agent runtime: `agent-framework`
Chat UX + multi-turn clarification + Azure AI Foundry / Azure OpenAI signals select the
**agent-framework** runtime. The Foundry hosted prompt-agent is preferred when configured;
the deterministic local orchestration path is the always-on fallback so the service stays
online even without Foundry. Recorded as `agent_runtime: agent-framework`.

## ADR-3 — Retrieval pattern: `azure_ai_search` (not `file_search`)
Per the `knowledge-retrieval-architect` Decision Rule, the corpus already lives in
enterprise systems (SharePoint + Blob), requires metadata/provenance filtering, incremental
sync, and multimodal enrichment. These cannot be expressed by Foundry-managed `file_search`,
so the pattern is **`azure_ai_search`** — a real pull-model index with a skillset.
See `docs/retrieval/retrieval-design.json`.

> **Amended by ADR-10.** The in-process hybrid+semantic query (`retrieval/query.py`) is now
> the *offline fallback* rather than the primary query-time retrieval path. The same
> `azure_ai_search` index is still the system of record; ADR-10 moves query-time retrieval
> onto a Foundry IQ knowledge base layered over that index.

## ADR-4 — Three indexer paths
Binary documents (PDF/Office) need layout extraction + multimodal enrichment; `.md` and
`.json` are text-native and skip the heavy enrichment. Splitting into **multimodal**,
**markdown**, and **json** indexers keeps each skillset minimal and lets them run/retry
independently.

## ADR-5 — Incremental SharePoint sync over full re-crawl
Re-indexing the entire corpus on every run is wasteful and slow. A per-file high-water-mark
(stored in Cosmos) classifies `added`/`updated`/`unchanged`/`deleted`; only changed files
are uploaded to Blob, and the indexer is triggered **only** when the net change count is
positive (`added + updated + deleted > 0`).

## ADR-6 — Service Bus queue between scheduler and worker
Decoupling sync *requests* (scheduler/HTTP) from sync *execution* (worker) via a Service Bus
queue gives durable, retryable, back-pressure-friendly orchestration and lets the API stay
responsive.

## ADR-7 — Cosmos hierarchical partition key for chat history
`/tenantId` → `/userId` → `/conversationId` keeps each conversation's items physically
co-located, bounds partition size, and supports efficient multi-tenant history reads.

## ADR-8 — Identity-first security
No account keys. Managed identity for every hop and data-plane RBAC role assignments
(Cosmos SQL data role, Search Index Data roles, Storage Blob Data roles, Cognitive Services
OpenAI User). `disableLocalAuth` / `allowSharedKeyAccess=false` where supported. Validated by
`security-compliance-auditor` — see `docs/security/security-audit.json`.

## ADR-9 — Container Apps host + Function App scheduler
The API + worker run on Azure Container Apps (scale-to-zero, managed identity, revisions).
The timer/HTTP scheduler runs as an Azure Functions app so the CRON trigger is a
first-class platform primitive rather than a hand-rolled loop.

## ADR-10 — Query-time retrieval: Foundry IQ knowledge base (primary), hybrid query (fallback)
Adopted from the upstream `case-assistant-agent` "foundry-iq-v1" update. A **Foundry IQ
knowledge base** (`casewright-kb`) is provisioned over the existing `casewright-index` via
the search service's preview knowledge-base REST API. The knowledge base is itself an MCP
server (`<search>/knowledgebases/casewright-kb/mcp`) exposing the `knowledge_base_retrieve`
tool. The hosted Foundry agent owns retrieval: a RemoteTool project connection
(`casewright-kb-mcp`, ProjectManagedIdentity auth) binds the agent's `mcp` tool to that
endpoint, so the agent retrieves + reranks server-side and returns grounded citations.

Rationale:
- **Single grounding owner.** Retrieval, reranking, and reasoning effort live with the KB,
  not duplicated in app code; model/index/threshold changes are config, not redeploys.
- **No app-side query endpoint.** Casewright passes the bare question to the hosted agent;
  it never calls a query-time retrieve REST endpoint. The KB + agent handle retrieval.
- **ADR-2 still holds.** When Foundry is not configured, the deterministic local path runs
  the in-process hybrid+semantic query (`retrieval/query.py`) so the service always works
  locally. ADR-3's index is unchanged — Foundry IQ layers on top of it.

Provisioning is one-shot via `scripts/deploy_agent.py deploy` (KB + source + RemoteTool
connection + hosted agent). Tunables are under `SEARCH_KB_*` / `FOUNDRY_KB_CONNECTION_NAME`.
