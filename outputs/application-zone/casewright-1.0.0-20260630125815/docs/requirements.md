# Casewright — Business Requirements Document

> **Project:** Casewright — Agentic Case Knowledge Platform
> **Slug:** `casewright`
> **Source pattern:** internal agentic-RAG case assistant (re-architected from scratch in the Azure Architecture Factory)
> **Runtime:** agent-framework (LLM-driven chat + deterministic fallback)
> **Archetype:** rag-qa (corpus-grounded Q&A with multimodal ingestion)
> **Language:** Python 3.11 / FastAPI · **IaC:** Bicep · **Network tier:** vnet-integrated

## 1. Problem Statement

Case workers, analysts, and support engineers spend a large share of their time hunting
through scattered case files, SharePoint document libraries, PDFs, Office files, and
internal markdown/JSON knowledge to answer a single question. Knowledge is stale, hard to
cite, and not conversational.

Casewright is an Azure-native, agentic Retrieval-Augmented Generation (RAG) platform that
turns an organization's case corpus into a grounded, cited, multi-turn chat experience —
with an automated ingestion pipeline that keeps the index fresh from Blob Storage and
SharePoint.

## 2. Goals

| # | Goal |
|---|------|
| G1 | Conversational, grounded answers over the case corpus with inline citations. |
| G2 | Automated ingestion of binary documents (PDF/Office), markdown, and JSON into a vector + semantic search index. |
| G3 | Incremental SharePoint delta-sync that only re-indexes when content actually changes. |
| G4 | Durable, per-user, per-conversation chat history. |
| G5 | Scheduled and on-demand sync orchestration without manual operator steps. |
| G6 | Identity-first security — no account keys, managed identity and data-plane RBAC everywhere. |
| G7 | Optional Azure AI Foundry hosted prompt-agent path, with a deterministic fallback so the service never goes dark. |

## 3. In-Scope Functional Requirements

### 3.1 Chat & Retrieval (REQ-CHAT)
- **REQ-CHAT-1**: `POST /api/chat` accepts a user message + conversation id and returns a grounded answer with citations (document title + source path).
- **REQ-CHAT-2**: Multi-turn context — prior turns for the conversation are loaded from chat history and included in the prompt.
- **REQ-CHAT-3**: Retrieval uses **hybrid** search (vector + keyword) plus the semantic reranker, dropping matches below a configurable minimum reranker score.
- **REQ-CHAT-4**: Two runtimes — a Foundry hosted **prompt-agent** path when configured, and a deterministic local orchestration path as guaranteed fallback.
- **REQ-CHAT-5**: `GET /api/chat/{conversation_id}` returns the conversation history.

### 3.2 Ingestion Pipeline (REQ-ING)
- **REQ-ING-1**: `POST /api/pipeline/setup-pipeline` creates/updates the Azure AI Search data source, index, skillsets, and indexers (idempotent).
- **REQ-ING-2**: Three indexer paths — **multimodal** (binary docs: PDF/Office), **markdown** (`.md`), and **json** (`.json`).
- **REQ-ING-3**: Blob data source with **change tracking** (high-water-mark) and **soft-delete** detection.
- **REQ-ING-4**: Skillsets perform extraction, chunking, embedding, and multimodal enrichment (image verbalization).
- **REQ-ING-5**: `POST /api/pipeline/run-indexer` triggers an indexer run; `GET /api/pipeline/indexer-status` returns indexer execution status.

### 3.3 SharePoint Delta Sync (REQ-SP)
- **REQ-SP-1**: `GET /api/sharepoint/sites`, `/sites/member-of`, `/sites/members` enumerate sites and membership.
- **REQ-SP-2**: `POST /api/sharepoint/sites/sync-site` and `/sites/sync` queue per-site sync requests.
- **REQ-SP-3**: Per-file change detection classifies each file as `added`, `updated`, `unchanged`, or `deleted`.
- **REQ-SP-4**: Only changed files are uploaded to Blob Storage; sync state (high-water-mark per file) is persisted in Cosmos DB.
- **REQ-SP-5**: Sync requests are scheduled through a Service Bus queue.

### 3.4 Queue Worker (REQ-WORK)
- **REQ-WORK-1**: A background worker consumes Service Bus sync messages and runs the SharePoint sync job for the requested site.
- **REQ-WORK-2**: The worker triggers a search indexer run **only** when `added + updated + deleted > 0`; it skips when nothing changed (all-unchanged or zero-discovery runs).

### 3.5 Chat History Store (REQ-HIST)
- **REQ-HIST-1**: Cosmos DB stores chat history using a **hierarchical partition key** (`/tenantId`, `/userId`, `/conversationId`).
- **REQ-HIST-2**: Sync state documents share the Cosmos account in a dedicated container.

### 3.6 Scheduler Function App (REQ-SCHED)
- **REQ-SCHED-1**: Timer trigger `ScheduleSharePointSync` enqueues sync requests on a CRON schedule (`SHAREPOINT_SYNC_SCHEDULE`).
- **REQ-SCHED-2**: HTTP trigger `POST /api/schedule/sharepoint-sync` enqueues on demand.

### 3.7 Frontends (REQ-UI)
- **REQ-UI-1**: A lightweight web chat client for developer testing (calls `/api/chat`).
- **REQ-UI-2**: A Microsoft 365 / Teams bot channel for end-user access.

## 4. Non-Functional Requirements
- **NFR-SEC-1**: No account/connection-string keys for Search, Storage, Cosmos, OpenAI, or Service Bus where managed identity is feasible. `disableLocalAuth` / `allowSharedKeyAccess=false` where supported.
- **NFR-SEC-2**: Data-plane RBAC assignments for Cosmos (SQL data-plane role), Search (Index Data roles), Storage (Blob Data roles), and Azure OpenAI (Cognitive Services OpenAI User).
- **NFR-NET-1**: VNet-integrated network tier with private connectivity to data services.
- **NFR-OBS-1**: Application Insights wired via `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- **NFR-REL-1**: All pipeline/setup operations are idempotent and safe to re-run.

## 5. Declared Agents (Phase 1.5 input)

```yaml
implementation:
  agents:
    - name: case-knowledge-agent
      role: "Grounded multi-turn Q&A over the enterprise case corpus with citations."
      corpus:
        sources: [sharepoint, blob]
        scale: enterprise
        enrichment: multimodal
        metadata_filtering: true
        incremental_sync: true
      tools: [azure_ai_search, function_calling]
```

## 6. Out of Scope
- Authoring/editing of source case documents (read-only corpus).
- Non-Azure search or storage backends.
- Fine-tuning of the base chat model.
