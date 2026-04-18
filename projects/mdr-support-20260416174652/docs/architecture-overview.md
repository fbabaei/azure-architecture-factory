# MDR Arrangement Extraction Agent - Architecture Overview

## Purpose
Phase 1 of the EY Tax MDR (Mandatory Disclosure Rules) compliance agent:
ingest unstructured arrangement documents (PDF, text), extract a
structured `MDRArrangement` JSON payload, and drive a human-in-the-loop
clarification chat that fills any missing mandatory fields before a
draft arrangement is issued.

This implementation now follows a two-agent target design:
- Chat Agent: user-facing orchestration, intent routing, off-topic guardrail,
  and follow-up prompts.
- Extraction Agent: specialist extraction and structured output generation.

The system supports three feature paths:
- F1: compliance Q&A chat (RAG-ready with retrieval hook).
- F2: document upload to case draft.
- F3: free-text prompt to case draft with missing-field follow-up.

## Alignment With Compliance-Agent Technical Design
This architecture is aligned with the
[Compliance Intelligence Agent – Technical Design](https://github.com/aishwaryaumachandran/compliance-agent/blob/main/docs/Technical-Design.md)
(April 16, 2026). Mapping:

| Reference design element | MDR implementation |
|---|---|
| Three features (F1 Q&A, F2 upload → draft, F3 text → draft with follow-up) | `POST /api/chat`, `POST /api/upload`, `POST /api/case/from-text` |
| Two-agent topology (Chat Agent + Extraction Agent) orchestrated via Microsoft Agent Framework | `ChatOrchestratorAgent` + `ExtractionSpecialistAgent` (see [`AGENT_FRAMEWORK_RUNTIME_PATTERN`](../../../docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md)) |
| GPT-5.2 as primary model (chat + vision) | `AZURE_OPENAI_DEPLOYMENT=gpt-5.2`; `gpt-4o` retained as back-compat fallback via redeployment only |
| `text-embedding-3-small` for RAG | `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-3-small` |
| Azure AI Content Understanding (optional) OR GPT-5.2 vision direct | Phase 1 uses **Azure AI Document Intelligence `prebuilt-layout`**; Phase 2 swaps in Content Understanding or GPT-5.2 vision behind the same `document_ingestion` service |
| Azure AI Search — hybrid RAG (vector + keyword + semantic reranking) | `contentVector` field + `default` semantic configuration; bootstrapped by `scripts/bootstrap_search_index.py` |
| Cosmos DB containers: sessions, case-drafts, audit-log | `arrangements`, `sessions`, `case-drafts`, `audit-log` |
| Structured output mode for schema-safe extraction | OpenAI JSON mode + post-generation `MDRArrangement` Pydantic validation |
| Three-layer off-topic guardrail (system prompt + intent classifier + keyword fallback) | `guardrails.py` implements all three layers |
| Human-in-the-loop loop | `chat_session.handle_chat_turn` + `apply_answer_to_arrangement` with forward-progress safety net |
| Session state in Cosmos (survives restart, multi-user concurrent) | `sessions` container keyed by `session_id` (= `arrangement_id`) |
| Application Insights telemetry + prompt logging | `azure-monitor-opentelemetry` wiring |

Deviations from the reference, with rationale:

| Reference choice | MDR choice | Reason |
|---|---|---|
| .NET 8 + AgentBuilder | Python 3.13 + `Agent(client, name, ...)` | Factory Python convention; semantics are identical |
| App Service or Functions | **Container Apps** | Same runtime envelope the factory uses elsewhere; KEDA scale-to-zero |
| React or Blazor chat UI | Not in Phase 1 | API-first; UI deferred to Phase 2 |

## BRD Requirement Traceability
- **Compliance agent supporting MDR-specific Q&A and arrangement creation**
  -> Container-hosted FastAPI agent fronted by API Management, with
    `/api/chat` intent routing and Q&A handling.
- **File upload-based extraction**
  -> `POST /api/upload` (alias to `POST /arrangements/upload`) -> Blob Storage
    + Document Intelligence layout model -> Azure OpenAI structured extraction.
- **Text prompt-based extraction**
  -> `POST /api/case/from-text` -> Extraction Agent -> clarification loop for
    missing mandatory fields.
- **Interactive, human-in-the-loop chat**
  -> `POST /api/chat` and `POST /arrangements/{id}/chat` +
    `GET /arrangements/{id}/clarifications`, backed by a session store in
    Cosmos DB.
- **Clarification loop for missing mandatory fields**
  -> `clarification_service` scans the draft against `MANDATORY_FIELDS`
     and produces `ClarificationQuestion` prompts for the next missing field.
- **Draft arrangement output in JSON**
  -> `POST /api/case/{id}/confirm` (alias to `POST /arrangements/{id}/draft`)
    returns the finalised
     `MDRArrangement` JSON.
- **Batch / multi-arrangement processing deferred**
  -> No batch endpoints, no queue worker in the diagram - by design.

## Azure Building Blocks
| Concern | Service | Reference-design alignment |
|---------|---------|----------------------------|
| API gateway, JWT validation, rate limiting | Azure API Management | API surface matches §8 of reference |
| Compute for the agent API | Azure Container Apps | Reference allows App Service or Functions; Container Apps is the factory equivalent |
| LLM extraction, clarification, Q&A synthesis | Azure OpenAI — `gpt-5.2` (chat + vision) | D1: GPT-5.2 primary |
| Embeddings for RAG indexing | Azure OpenAI — `text-embedding-3-small` | §2 target state |
| PDF layout / text extraction | Azure AI Document Intelligence `prebuilt-layout` | Phase 1 substitute for Content Understanding / vision; see §6.1 of reference |
| Knowledge retrieval (RAG) | Azure AI Search — hybrid (vector + keyword + semantic rerank) | D6 of reference |
| Source document persistence | Azure Blob Storage — `mdr-documents` | §7 reference |
| Knowledge-base source files | Azure Blob Storage — `knowledge-base-source` | §7 reference |
| Arrangement drafts + chat session state + audit trail | Azure Cosmos DB (serverless) — `arrangements`, `sessions`, `case-drafts`, `audit-log` | D4 of reference |
| Secrets + config | Azure Key Vault | §7 reference |
| Workload identity | User-assigned Managed Identity | §10 reference |
| Telemetry, metrics, logs, prompt logging | Application Insights + Log Analytics | §7 reference |

All service-to-service auth uses managed identity + RBAC
(`disableLocalAuth: true` on OpenAI, Document Intelligence, Cosmos).

## Network Topology
Phase 1 is deployed on the public network tier as declared in the BRD
options. Production roll-out should migrate to a VNet-integrated
Container Apps environment with private endpoints for Cosmos, Blob,
Key Vault, OpenAI and Document Intelligence.

## Artefact Map
- Detailed architecture document: `docs/detailed-architecture.md`.
- Overview diagram: `diagrams/mdr-support-20260416174652.drawio`.
- Detailed architecture diagram: `diagrams/mdr-support-20260416174652-detailed-architecture.drawio`.
- Infrastructure: `infra/main.bicep`.
- Source: `src/mdr_agent/`.

## Target State Notes
- GPT-5.2 is the default model; redeployment to a different Azure OpenAI
  deployment name (e.g. `gpt-4o`) is supported without code changes via the
  `AZURE_OPENAI_DEPLOYMENT` env var.
- Document pipeline can be switched to Azure AI Content Understanding or
  direct GPT-5.2 vision by swapping the implementation of
  `document_ingestion.py` — interface is stable.
- Off-topic guardrail is layered (system prompt + intent classifier tool +
  keyword fallback) per §6.4 of the reference design.
