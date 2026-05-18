# MDR Support — Gap Analysis vs. Reference Technical Design

- **Date:** 2026-04-17
- **Reviewer model:** Claude Opus 4.7
- **Reviewer role:** Danny — Lead / Architect
- **Project:** `projects/mdr-support-20260416174652`
- **Reference design:** [`aishwaryaumachandran/compliance-agent — docs/Technical-Design.md`](https://github.com/aishwaryaumachandran/compliance-agent/blob/main/docs/Technical-Design.md) (Phase 1, Compliance Intelligence Agent)
- **Scope:** End-to-end conformance of the regenerated MDR extraction agent against the reference design's three features (F1/F2/F3), tech stack, agent topology, API surface, data flows, Azure resource topology, key components, and design decisions (D1–D7). Evidence gathered by reading the application source, tests, Bicep, and spot-checking the architecture diagram. No source code or diagrams were modified.

---

## 1. Executive Summary

- **Overall alignment: ~55%.** The project delivers the *shape* of the reference design (three features, RAG/extraction/HITL story, Azure OpenAI + Blob + Cosmos + AI Search topology) but diverges materially on the implementation stack (Python/FastAPI vs .NET 8), the agent runtime (custom service orchestration vs Microsoft Agent Framework), and the model (gpt-4o vs gpt-5.2).
- **F1 (Q&A) is the closest match** — an Azure OpenAI–grounded `/qa` and `/api/chat` path with an optional AI Search retrieval step, an off-topic guardrail, and a deterministic local fallback. Hybrid vector+keyword search with a semantic reranker is **not** present; retrieval is a plain semantic text query against AI Search with no embedding pipeline and no chunking policy.
- **F2 and F3 are functionally wired** (upload → extract → clarify → confirm), but HITL is driven by a deterministic state machine over `MANDATORY_FIELDS`, not by a Chat Agent invoking an Extraction Agent through an agent framework. There is no two-agent topology at runtime — there is one orchestrating service plus two LLM callers.
- **Biggest gaps:** (i) no Microsoft Agent Framework / two-agent runtime; (ii) model is gpt-4o, not gpt-5.2, and no vision path; (iii) no embedding model / semantic chunking / hybrid-search reranker (i.e., the RAG component is architecturally thin); (iv) no Content Understanding path or vision-direct alternative; (v) no structured-output schema validator beyond Pydantic parse-or-fall-back; (vi) no UI (React/Blazor) in-repo; (vii) Cosmos containers `case-drafts` and `audit-log` are provisioned but never written.
- **Go/No-Go posture for Phase 1:** **Go for a functional demo / internal pilot.** **No-go for production compliance delivery** until the agent-framework wiring, structured-output validation, RAG hardening, and audit-log persistence land. The local fallbacks make the happy path demonstrable offline, which is the right Phase 1 accelerator, but they mask meaningful production gaps.

---

## 2. Validation Evidence

| Check | Command | Result |
|---|---|---|
| Unit + integration smoke | `python -m pytest projects/mdr-support-20260416174652/tests/test_generated_project.py -v` | **12 passed in 0.89s** |
| Liveness probe | `GET /health` via `TestClient` | `200 {"status":"ok","timestamp":"2026-04-17T23:33:49.119582+00:00","azure_enabled":false}` |
| Route discovery | `sorted({r.path for r in app.routes})` | 17 routes (see Appendix A) |
| Repository backend (local) | `config.azure_enabled == False` ⇒ `InMemoryRepository` | Confirmed by [`repository.py` L128–L135](../src/mdr_agent/services/repository.py) |
| Extraction backend (local) | No `AZURE_OPENAI_ENDPOINT` ⇒ `HeuristicExtractionAgent` | Confirmed by [`extraction_agent.py` L147–L152](../src/mdr_agent/services/extraction_agent.py) |
| Ingestion backend (local) | No `AZURE_BLOB_ACCOUNT_URL` ⇒ `LocalDocumentIngestion` | Confirmed by [`document_ingestion.py` L97–L101](../src/mdr_agent/services/document_ingestion.py) |

`azure_enabled=false` in the health payload matches the config logic: `azure_enabled` requires **both** `AZURE_OPENAI_ENDPOINT` and `AZURE_BLOB_ACCOUNT_URL` to be set ([`config.py` L54–L57](../src/mdr_agent/config.py)).

---

## 3. Feature Coverage (F1 / F2 / F3)

| Ref feature | Reference design intent | Implemented endpoint(s) | Implementation files | Status |
|---|---|---|---|---|
| **F1 Compliance Q&A Chat (RAG)** | `/api/chat` with RAG (hybrid vector+keyword + semantic reranker), off-topic guardrail, conversation memory | `POST /api/chat`, `POST /qa` | [`main.py` `api_chat()` L199–L226](../src/mdr_agent/main.py), [`qa_service.py` `AzureOpenAIQAService` L123–L198](../src/mdr_agent/services/qa_service.py), [`guardrails.py`](../src/mdr_agent/services/guardrails.py) | 🟡 **Partial** — endpoint + guardrail + AI Search POST exist, but retrieval is keyword semantic search only (no vector, no reranker config beyond `semanticConfiguration: "default"`), no embedding pipeline, no chunking policy. |
| **F2 Document Upload → Case Draft** | Blob upload → Content Understanding OR GPT vision → Extraction Agent → Chat Agent confirms → schema validation | `POST /api/upload` (alias of `POST /arrangements/upload`) | [`main.py` `upload_document()` L115–L146, `api_upload_document()` L171–L177](../src/mdr_agent/main.py), [`document_ingestion.py` `AzureDocumentIngestion` L74–L104](../src/mdr_agent/services/document_ingestion.py), [`extraction_agent.py` `AzureOpenAIExtractionAgent` L107–L144](../src/mdr_agent/services/extraction_agent.py) | 🟡 **Partial** — Blob upload + Document Intelligence `prebuilt-layout` path is implemented; no Content Understanding, no GPT vision, no structured-output mode beyond `response_format={"type":"json_object"}`, no post-gen validator beyond Pydantic. |
| **F3 Text Prompt → Case Draft (HITL)** | Text → Extraction Agent → HITL loop until schema-valid | `POST /api/case/from-text`, `POST /api/chat` (when session has a case), `POST /arrangements/{id}/chat`, `POST /api/case/{id}/confirm` | [`main.py` `create_case_from_text()` L180–L196, `api_chat()` L199–L226, `api_confirm_case()` L296–L298](../src/mdr_agent/main.py), [`chat_session.py` `handle_chat_turn()` L58–L111](../src/mdr_agent/services/chat_session.py), [`clarification_service.py`](../src/mdr_agent/services/clarification_service.py) | ✅ **Implemented** (functionally) — but HITL is a deterministic state machine over `MANDATORY_FIELDS`, not an LLM-driven loop. See Agent Architecture (§5) and Data Flow (§7). |

---

## 4. Tech Stack Alignment

| Reference component | Implemented equivalent | Delta |
|---|---|---|
| Azure OpenAI **gpt-5.2** (chat + vision) | Azure OpenAI **gpt-4o** (chat only) — default deployment in `config.py` L19 and `main.bicep` L24–L27 | ❌ **Model mismatch.** No vision path wired; `extraction_agent.py` sends text-only chat completions. |
| `text-embedding-3-small` | ❌ No embedding model configured, provisioned, or called | ❌ **Missing.** No embeddings in `config.py`, no deployment in `main.bicep`, no embedding call in `qa_service.py` or `document_ingestion.py`. |
| **Microsoft Agent Framework** (multi-agent orchestrator) | ❌ Custom FastAPI service with direct Azure OpenAI client calls (`openai.AzureOpenAI`) | ❌ **Missing.** No `Microsoft.Agents` / `AgentBuilder` / `WithModel` / `WithStructuredOutput` usage anywhere. No agent runtime. |
| Azure AI Content Understanding (optional) **OR** GPT-5.2 vision direct | Azure AI Document Intelligence (`prebuilt-layout`) | 🟡 **Substitute, not equivalent.** Document Intelligence returns lines/pages; Content Understanding would return a semantic field schema. No vision-direct alternative. |
| Azure AI Search (hybrid vector + keyword + semantic reranker) | Azure AI Search (semantic query, top=3) | 🟡 **Partial.** `qa_service.py` L150–L168 posts `queryType: "semantic"` with `semanticConfiguration: "default"` — but no `vectorQueries`, no embedding generation, no hybrid retrieval. Index schema is not defined in Bicep. |
| Azure Blob Storage (2 containers: `uploaded-documents`, `knowledge-base-source`) | Azure Blob Storage (2 containers: `mdr-documents`, `knowledge-base-source`) | ✅ **Aligned** (naming differs; `knowledge-base-source` is provisioned but nothing reads/writes it). |
| Azure Cosmos DB (containers: `sessions`, `case-drafts`, `audit-log`) | Azure Cosmos DB (containers: `arrangements`, `sessions`, `case-drafts`, `audit-log`) | 🟡 **Infra-only for two containers.** Bicep provisions all four; application only touches `arrangements` and `sessions` ([`repository.py` L70–L79](../src/mdr_agent/services/repository.py)). `case-drafts` and `audit-log` are unused. |
| **.NET 8 ASP.NET Core backend** | **Python 3 / FastAPI** (`fastapi`, `uvicorn`) | ❌ **Language/runtime mismatch.** Entire server is Python. Not a gap vs the *repo's* stated architecture, but a direct gap vs the reference technical design. |
| **React or Blazor chat UI** | ❌ No UI in repo; API only | ❌ **Missing.** No `web/`, `ui/`, `static/`, or SPA build artifact in the project tree. |
| Application Insights | Application Insights (`azure.monitor.opentelemetry.configure_azure_monitor`) | ✅ **Aligned** — enabled when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set ([`main.py` L63–L71](../src/mdr_agent/main.py)). |
| API Management (front door) | APIM provisioned; not wired | 🟡 **Provisioned only.** `main.bicep` L294–L305 creates an APIM Developer instance with no API, operation, backend, JWT policy, or rate-limit policy. |

---

## 5. Agent Architecture — Reference vs Actual

**Reference:** two-agent topology over Microsoft Agent Framework.
- **Chat Agent** — RAG Q&A, conversation, guardrails, invokes Extraction Agent as a tool, drives HITL.
- **Extraction Agent** — ingest, field extraction, classification reasoning (CoT + confidence), jurisdiction validation, missing-field detection, structured JSON output.
- Orchestrator = Microsoft Agent Framework with `AgentBuilder`, `WithModel("gpt-5.2")`, `WithStructuredOutput<ChatResponse>` / `<CaseDraft>`.

**Actual:** single-process FastAPI service orchestrating two *service classes* that each make direct Azure OpenAI calls.

| Reference agent | Actual component | Match? |
|---|---|---|
| Chat Agent | `api_chat()` dispatcher in [`main.py` L199–L226](../src/mdr_agent/main.py) — routes to guardrail → Q&A service → chat-session handler | 🟡 **Dispatcher, not an agent.** No tool-calling, no agent loop; behavior is a three-way if/else on session state. |
| Extraction Agent | [`ExtractionAgent` protocol](../src/mdr_agent/services/extraction_agent.py) with `AzureOpenAIExtractionAgent` + `HeuristicExtractionAgent` fallback | 🟡 **Exists as a service, not an agent.** Single LLM call, no CoT prompt, no per-field confidence, no jurisdiction validator, no missing-field reasoning (missing-fields is computed by [`clarification_service.find_missing_fields`](../src/mdr_agent/services/clarification_service.py) — a pure function). |
| Orchestrator (Microsoft Agent Framework) | FastAPI + `functools.lru_cache` singletons | ❌ **Missing.** No framework, no agent graph, no message bus, no tool registry. |
| Chat Agent invokes Extraction Agent (tool pattern) | `api_chat()` never calls `ExtractionAgent.extract()`; extraction is invoked only from `upload_document` and `create_case_from_text` | ❌ **Flow mismatch.** In the reference design the Chat Agent drives extraction through HITL; here the clarification loop is deterministic Pydantic field-presence checking. |
| Classification reasoning (CoT + high/med/low confidence) | `confidence = filled / 6.0` in [`extraction_agent.py` L130–L142](../src/mdr_agent/services/extraction_agent.py) | ❌ **Not classification reasoning.** Confidence is a field-completeness ratio, not an LLM-expressed confidence band over the hallmark classification. |

**Summary:** the project has two *services*, not two *agents*. The runtime abstraction (Microsoft Agent Framework) called out as the core orchestration substrate (D2, reference doc) is absent.

---

## 6. API Surface — Reference 8 vs Implemented 17

| Reference endpoint | Implemented match | Extra / legacy |
|---|---|---|
| `POST /api/chat` | ✅ [`main.py` L199](../src/mdr_agent/main.py) |  |
| `POST /api/upload` | ✅ [`main.py` L171](../src/mdr_agent/main.py) (thin wrapper over `/arrangements/upload`) |  |
| `POST /api/session` | ✅ [`main.py` L149](../src/mdr_agent/main.py) |  |
| `GET /api/session/{id}` | ✅ [`main.py` L154](../src/mdr_agent/main.py) |  |
| `DELETE /api/session/{id}` | ✅ [`main.py` L163](../src/mdr_agent/main.py) |  |
| `GET /api/case/{id}` | ✅ [`main.py` L282](../src/mdr_agent/main.py) |  |
| `PUT /api/case/{id}` | ✅ [`main.py` L286](../src/mdr_agent/main.py) |  |
| `POST /api/case/{id}/confirm` | ✅ [`main.py` L296](../src/mdr_agent/main.py) |  |
| — | — | 🟡 **Extra:** `POST /api/case/from-text` (not in reference's 8; reasonable F3 addition). |
| — | — | 🟡 **Legacy / parallel surface:** `POST /arrangements/upload`, `GET /arrangements/{id}`, `GET /arrangements/{id}/clarifications`, `POST /arrangements/{id}/chat`, `POST /arrangements/{id}/draft`. These duplicate the `/api/*` surface with different response shapes (`ChatResponse` vs `ApiChatResponse`). |
| — | — | ✅ **Extra:** `POST /qa` (explicit Q&A endpoint, lean variant of `/api/chat`'s QA branch). |
| — | — | ✅ Standard: `/health`, `/docs`, `/docs/oauth2-redirect`, `/openapi.json`, `/redoc`. |

**Delta:** 17 routes total (9 domain + 5 framework + 3 surplus domain routes). The `/arrangements/*` surface is a **duplicate API shape** — same behavior, different paths and response models. It should either be deprecated or explicitly documented as the internal flavor.

---

## 7. Data Flow Fidelity

### F1 — Compliance Q&A (RAG)

- **Reference:** user → Chat Agent → off-topic guardrail → hybrid search (vector + keyword) + semantic reranker → prompt with retrieved context → response.
- **Actual:** `api_chat()` → [`is_off_topic()`](../src/mdr_agent/services/guardrails.py) (regex blocklist + compliance-hint allowlist) → if no case in session, `QAService.answer()` → if `AZURE_AI_SEARCH_*` all set, POST to `{endpoint}/indexes/{index}/docs/search?api-version=2024-07-01` with `queryType: "semantic"`, `top: 3`. No `vectorQueries`. No chunking. No reranker beyond the semantic configuration.
- **Verdict:** 🟡 Partial. Endpoint + guardrail + optional retrieval exist. Retrieval is not hybrid; index shape is not defined; embeddings are not produced.

### F2 — Upload → Case Draft

- **Reference:** Blob upload → Content Understanding OR GPT vision → Extraction Agent → Chat Agent confirmation HITL → schema validation.
- **Actual (Azure path):** `POST /api/upload` → `AzureDocumentIngestion.ingest()` uploads bytes to Blob, runs `prebuilt-layout` via Document Intelligence, joins lines into `text` → `AzureOpenAIExtractionAgent.extract(text)` → `ExtractionResult` persisted via `_repo().save()` → caller must drive the HITL loop via `/api/chat` (after the case is in the session).
- **Actual (local path):** `LocalDocumentIngestion` decodes bytes as UTF-8 (no PDF handling); `HeuristicExtractionAgent` runs regex for reference / hallmark codes / jurisdiction codes / implementation date.
- **Verdict:** 🟡 Partial. Blob + Document Intelligence flow is correct in shape. No Content Understanding. No vision. Schema validation is Pydantic parse; invalid output silently degrades to `payload = {}` ([`extraction_agent.py` L127–L128](../src/mdr_agent/services/extraction_agent.py)), which produces an empty arrangement rather than a validator error.

### F3 — Text → Case Draft (HITL)

- **Reference:** text → Extraction → HITL loop driven by the Chat Agent until the schema validates.
- **Actual:** `POST /api/case/from-text` → `_extractor().extract(payload.text)` → save. HITL is then driven by `POST /api/chat` (session has a case → `handle_chat_turn`) OR the legacy `/arrangements/{id}/chat`. The loop logic:
  1. Compute `pre_bundle = build_clarifications(arrangement)` — deterministic `MANDATORY_FIELDS` check.
  2. Take `answered_field = pre_bundle.missing_fields[0]`.
  3. `_apply_answer_to_arrangement` — scalar assignment for `reference` / `summary` / `implementation_date`; comma-split for `jurisdictions` / `hallmarks` / `parties` ([`chat_session.py` L20–L58](../src/mdr_agent/services/chat_session.py)).
  4. Recompute `post_bundle`; return next question or "complete" message.
- **Verdict:** ✅ Functionally implemented, 🟡 design-level divergence. The loop is deterministic state-machine HITL, not LLM-driven. A user answer like `"Acme LuxCo (intermediary, LU); Acme IE (relevant_taxpayer, IE)"` will be stored as **two parties both with role `relevant_taxpayer` and no jurisdiction**, because the parser ([`chat_session.py` L50–L56](../src/mdr_agent/services/chat_session.py)) discards everything but the name and hardcodes `role="relevant_taxpayer"`. This is explicitly called out in the code comment as a deferred LLM structured-extraction step.

---

## 8. Azure Resource Topology (Three-Way Comparison)

| Resource | Reference design | `infra/main.bicep` | `diagrams/mdr-support-20260416174652.drawio` |
|---|---|---|---|
| Azure OpenAI (chat) | ✅ gpt-5.2 | ✅ `openAiDeployment` default `gpt-4o`, version `2024-08-06` (L24–L27, L233–L240) | ✅ labeled `Azure OpenAI (gpt-4o)` |
| Azure OpenAI (embeddings) | ✅ `text-embedding-3-small` | ❌ Not deployed | ❌ Not shown |
| Content Understanding | ✅ (optional) | ❌ Not provisioned | ❌ Not shown |
| Document Intelligence | — (alternative path) | ✅ `documentIntelligence` (L242–L254) | ✅ shown |
| Azure AI Search | ✅ | ✅ `aiSearch` (basic SKU, L223–L232) | ✅ shown (labeled "optional RAG") |
| Storage Account | ✅ 2 containers | ✅ `storage` + `mdr-documents` + `knowledge-base-source` (L108–L136) | ✅ shown (single blob node) |
| Cosmos DB | ✅ `sessions`, `case-drafts`, `audit-log` | ✅ `arrangements`, `sessions`, `case-drafts`, `audit-log` (L138–L197) | ✅ shown (labeled `drafts + sessions` — under-represents the 4 containers) |
| App Service / Functions | ✅ | 🟡 Substituted with **Container Apps** (`mdrAgent`, L271–L292) | ✅ shown as Container Apps |
| Static Web App | ✅ | ❌ Not provisioned | ❌ Not shown |
| Application Insights | ✅ | ✅ `appInsights` (L74–L83) | ✅ shown |
| Resource Group | ✅ | Implicit (`targetScope = 'resourceGroup'`, L1) | — |
| Entra ID app reg | ✅ | ❌ Not in Bicep | ✅ shown as "Entra ID" upstream of APIM |
| Managed Identity | ✅ | ✅ `managedIdentity` (L45–L50) | ✅ shown |
| Key Vault | ✅ (secrets) | ✅ `keyVault` (L52–L63) | ❌ **Not shown as a node** (only a "secrets" edge label) |
| Log Analytics | — (implied by AI) | ✅ `logAnalytics` (L65–L73) | ✅ shown (combined with App Insights node) |
| Action Group (alerts) | — | ✅ (conditional, L85–L100) | ❌ Not shown |
| API Management | — (reference doesn't explicitly name APIM; implied by JWT + rate limit) | ✅ `apim` (L294–L305) | ✅ shown |
| Role assignments (RBAC) | ✅ (managed identity least-privilege) | ❌ **None declared** in Bicep | — |

**Delta summary:**
- Bicep is richer than the reference in some places (APIM, Log Analytics, action group) and poorer in others (no embedding deployment, no Static Web App, **no role assignments**).
- The diagram lists all compute/data planes but **omits Key Vault as a node** (only shows it on an edge label) and under-represents Cosmos (4 containers provisioned, label says "drafts + sessions").
- **gpt-4o vs gpt-5.2** is visible on the diagram, directly reflecting decision D1's non-adherence.

---

## 9. Key Components

| Component | Reference | Status | Evidence |
|---|---|---|---|
| Semantic chunking (~500–800 tokens) | Required for knowledge-base ingestion | ❌ **Missing** | No chunking code; no knowledge-base ingest pipeline. `knowledge-base-source` container exists but nothing writes to it. |
| Hybrid search (vector + keyword) | Required | ❌ **Missing** | `qa_service.py` L150–L168 posts `queryType: "semantic"` only — no `vectorQueries` array, no `vectorFields`. |
| Semantic reranker | Required | 🟡 **Partial / default** | Uses `semanticConfiguration: "default"`. The reranker *could* be enabled if the index is configured for it, but the index schema is not defined anywhere in the repo — so this is aspirational. |
| Embeddings (`text-embedding-3-small`) | Required | ❌ **Missing** | No model deployed, no embedding calls. |
| Classification reasoning (CoT + high/med/low confidence) | Required | ❌ **Missing** | `SYSTEM_PROMPT` in [`extraction_agent.py` L22–L44](../src/mdr_agent/services/extraction_agent.py) does not request CoT or a confidence label; confidence is `filled_fields / 6`. |
| Off-topic guardrail (system prompt + intent classifier + keyword blocklist) | Required | 🟡 **Partial** | Implemented as regex blocklist + compliance hint allowlist ([`guardrails.py`](../src/mdr_agent/services/guardrails.py)). No intent classifier model; the Q&A system prompt also enforces scope, which counts as the "system prompt" layer. |
| Session / state persistence (Cosmos, versioned case drafts) | Required | 🟡 **Partial** | `InMemoryRepository` locally; `CosmosRepository` when `cosmos_endpoint` is set. **No versioning** — `upsert_item` replaces; `case-drafts` container is never written. |
| Schema validation (structured-output mode + post-gen validator) | Required | 🟡 **Partial** | `response_format={"type":"json_object"}` is used ([`extraction_agent.py` L115–L124](../src/mdr_agent/services/extraction_agent.py)). Not the stronger Pydantic/JSON-Schema structured-output mode. Post-gen validator = `MDRArrangement.model_validate` + silent fallback to `{}` on JSON decode errors. |

---

## 10. Architecture Diagram Verification

Nodes observed (from `diagrams/mdr-support-20260416174652.drawio`):
`Tax Analyst`, `Entra ID`, `API Management (JWT + Rate Limit)`, `MDR Agent API (Container Apps)`, `Azure OpenAI (gpt-4o)`, `Document Intelligence`, `Azure AI Search (optional RAG)`, `Blob Storage (uploaded docs)`, `Cosmos DB (drafts + sessions)`, `Managed Identity`, `App Insights + Log Analytics`.

| Reference resource | In diagram? | Note |
|---|---|---|
| Azure OpenAI (gpt-5.2) | 🟡 Yes but labeled `gpt-4o` | **Visible drift vs D1.** |
| text-embedding-3-small | ❌ No | Missing. |
| Content Understanding | ❌ No | Missing (reference says "optional", so borderline). |
| Document Intelligence | ✅ Yes | Extra vs reference (substitute for Content Understanding). |
| AI Search | ✅ Yes | Labeled "optional RAG". |
| Blob Storage | ✅ Yes | Single node (two containers behind it). |
| Cosmos DB | 🟡 Yes | Label says "drafts + sessions"; actual provisioning is 4 containers — diagram under-represents. |
| App Service / Functions | 🟡 Substituted | Shown as Container Apps. |
| Static Web App | ❌ No | Missing (no UI in repo). |
| App Insights | ✅ Yes | Combined with Log Analytics. |
| Entra ID | ✅ Yes | Drawn as upstream auth source. |
| APIM | ✅ Yes | Drawn between Entra and Container Apps. |
| Managed Identity | ✅ Yes | Shown as separate node. |
| Key Vault | ❌ **Not shown as a node** | Only a "secrets" edge label. Given Bicep provisions it and `main.py` does not reference it, this is accurate *to the code* but inconsistent with the documented secret-management posture. |

**Drift to call out to the team:**
1. `Azure OpenAI (gpt-4o)` label ⇒ directly contradicts reference D1 (GPT-5.2).
2. Cosmos label `drafts + sessions` ⇒ understates the 4 containers actually provisioned (and overstates, since 2 of them are unused).
3. No embedding-model node, no Content Understanding, no Static Web App / UI.

---

## 11. Key Design Decisions (D1–D7)

| ID | Reference decision | Adherence | Evidence |
|---|---|---|---|
| **D1** | GPT-5.2 over GPT-4o-mini | ❌ **Does not adhere** | Default deployment is `gpt-4o` ([`config.py` L19](../src/mdr_agent/config.py); [`main.bicep` L24–L27](../infra/main.bicep)). |
| **D2** | Two-agent split (Chat Agent + Extraction Agent), Microsoft Agent Framework | ❌ **Does not adhere** | Two *services*, no agent framework. See §5. |
| **D3** | Content Understanding optional | 🟡 **Partial** | Substituted with Document Intelligence (different tool, similar slot). Acceptable substitution, but not the decision as stated. |
| **D4** | Cosmos DB for sessions | 🟡 **Partial** | Cosmos provisioned + used; `case-drafts` and `audit-log` containers are provisioned but not written. |
| **D5** | Structured output (GPT structured-output mode + post-gen validator) | 🟡 **Partial** | Uses JSON-object response format + Pydantic parse; silent degradation on JSON error (§9). |
| **D6** | Hybrid RAG (vector + keyword + semantic rerank) | ❌ **Does not adhere** | Semantic-only retrieval, no vector, no embeddings. See §9. |
| **D7** | Simple UI | ❌ **Does not adhere** | No UI in-repo. |

---

## 12. Critical Gaps (Ranked by Impact)

1. **C1. No Microsoft Agent Framework / two-agent runtime.** The orchestration substrate the reference design is built on is absent. **Impact:** every downstream "agentic" behavior (tool-calling, HITL agent loop, structured output typing, state handoff) is simulated with ad-hoc code. **Remediation effort: L.** Migrate Chat + Extraction services into an agent-framework runtime, or explicitly document FastAPI-service-oriented as the chosen deviation and rewrite decision D2.
2. **C2. Hybrid RAG is missing.** No embeddings, no vector index, no chunking, no knowledge-base ingest pipeline. **Impact:** F1 quality is bounded by the LLM's pretraining; "retrieved MDR context" is a keyword match at best. **Remediation effort: M.** Deploy `text-embedding-3-small`, add a chunker, define AI Search index schema (fields, vector fields, semantic config) in Bicep, add a KB ingest job.
3. **C3. Model mismatch (gpt-4o vs gpt-5.2) and no vision path.** D1 is the foundational model decision; diverging weakens reasoning quality for hallmark classification and blocks the vision-direct F2 branch. **Impact:** extraction quality ceiling is lower; no direct-image path if Document Intelligence is down. **Remediation effort: S.** Change deployment name + version once gpt-5.2 is available on the target Azure OpenAI region.
4. **C4. Structured-output validation silently degrades.** `json.JSONDecodeError` ⇒ `payload = {}` ([`extraction_agent.py` L126–L129](../src/mdr_agent/services/extraction_agent.py)) produces an empty arrangement instead of a 502 or a retry. **Impact:** a broken LLM response hides as a successful extraction with zero fields. **Remediation effort: S.** Switch to a strict structured-output mode (or JSON schema) and raise on parse failure.
5. **C5. Audit trail is provisioned but absent.** Bicep creates the `audit-log` Cosmos container; no code writes to it. No immutable event record for upload / extraction / HITL confirm / draft finalize. **Impact:** Phase 1 compliance claims about audit evidence are not substantiated. **Remediation effort: M.** Add an `AuditService` that writes append-only events for each lifecycle transition.

---

## 13. High / Medium Gaps

### High

6. **H1. `case-drafts` Cosmos container provisioned but unused.** Reference's "versioned case drafts" is not implemented; `save()` is an upsert. **Effort: M.**
7. **H2. Party/hallmark parsing is lossy.** `handle_chat_turn` hardcodes `role="relevant_taxpayer"` for all parsed parties and discards jurisdiction/TIN ([`chat_session.py` L50–L56](../src/mdr_agent/services/chat_session.py)). **Effort: M** — requires a structured-extraction LLM call per answer.
8. **H3. APIM provisioned without policies, operations, or backend binding.** JWT validation and rate limiting are a claim in the diagram and docs; no XML policy in `main.bicep`. **Effort: M.**
9. **H4. No role assignments in Bicep.** Managed identity exists; role bindings to OpenAI, Blob, Cosmos, Search, Document Intelligence, and Key Vault are not declared. **Effort: S–M.**
10. **H5. AI Search admin key injected via env var.** `AZURE_AI_SEARCH_API_KEY=aiSearch.listAdminKeys().primaryKey` ([`main.bicep` L287](../infra/main.bicep)) contradicts the managed-identity / Key Vault posture. **Effort: S.**
11. **H6. No project-local Dockerfile.** `main.bicep` L31 defaults to `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`; `DEPLOY.md` instructs building an image that has no `Dockerfile` source. **Effort: S.**
12. **H7. Duplicate API surface (`/arrangements/*` and `/api/*`).** Different response models, same behavior — invites drift. **Effort: S** (pick one; deprecate other).

### Medium

13. **M1. No `text-embedding-3-small` deployment.** Even if hybrid RAG is deferred, the embedding resource should be in Bicep to avoid a later capacity/region scramble. **Effort: S.**
14. **M2. AI Search index schema not defined.** No Bicep / code asset describes the `compliance-knowledge-base` index fields. **Effort: S.**
15. **M3. No Static Web App / UI.** Reference design includes a React/Blazor chat UI. **Effort: L** (new workstream).
16. **M4. Confidence is field-completeness, not LLM-expressed.** Reference wants high/med/low classification confidence. **Effort: S–M.**
17. **M5. Upload hardening is thin.** No size limit, MIME allowlist, or content-type/extension enforcement beyond "is empty". **Effort: S.**
18. **M6. No retry / timeout policy for external calls.** `openai.AzureOpenAI`, `DocumentIntelligenceClient`, `CosmosClient`, and `BlobServiceClient` calls run with library defaults; no circuit breaker or typed-failure translation. **Effort: S–M.**
19. **M7. Observability lacks domain events.** OpenTelemetry is configured; no custom spans / events for "extraction started", "HITL loop advanced", "draft finalized". **Effort: S.**
20. **M8. Diagram drift.** Shows `gpt-4o`, no Key Vault node, Cosmos under-described. **Effort: S.**

---

## 14. Residual Risks (Production Readiness)

- **R1. Public network access everywhere.** Cosmos, OpenAI, Document Intelligence, AI Search, Key Vault, and Storage all have `publicNetworkAccess: 'Enabled'`. Acceptable Phase 1 posture; not acceptable for regulated tax workloads without a documented exception.
- **R2. Container App ingress is `external: true`.** APIM is deployed but not the actual trust boundary. Any caller who guesses the Container App FQDN bypasses the gateway.
- **R3. Silent fallback behavior masks outages.** `qa_service.AzureOpenAIQAService._retrieve_context` swallows URL errors, timeouts, and JSON decode errors with a warning log ([`qa_service.py` L169–L174](../src/mdr_agent/services/qa_service.py)). Good for resilience, bad for observability — no metric is emitted, so a fully-degraded RAG path looks identical to a healthy one in App Insights.
- **R4. No persistence of uploaded documents in the local path.** `LocalDocumentIngestion` keeps bytes in a process-local dict; restart loses data. Only a demo concern, but easy to overstate what the local path validates.
- **R5. No test coverage for the Azure client paths.** All 12 tests run against fallback services. The Azure code paths (Blob upload, Document Intelligence, Cosmos, AI Search POST) are unexercised.

---

## 15. Recommended Next Actions (Prioritized)

1. **Close C3, C4, M4 together: switch to gpt-5.2 + structured output + LLM confidence.** Deploy gpt-5.2, switch `response_format` to a JSON-schema / typed-structured-output, add a `confidence` field to the schema and ask the model to emit it. (Effort S–M; highest quality win per hour.)
2. **Close C2 + M1 + M2: stand up the embedding deployment and AI Search index schema.** Even without the full ingest job, this unblocks hybrid RAG and makes the `knowledge-base-source` container meaningful. (Effort M.)
3. **Close C5 + H1: add `AuditService` and start using `audit-log` and `case-drafts` containers.** Versioned case drafts + append-only audit events are the compliance evidence Phase 1 promises. (Effort M.)
4. **Close C1: decide agent framework strategy.** Either migrate to Microsoft Agent Framework (preserve D2) or explicitly rewrite D2 and update the design docs to say "single service, two roles". Ambiguity here is the largest architectural risk. (Effort L if migrating; S if documenting the deviation.)
5. **Close H3 + H4 + H5: APIM policies, RBAC role assignments in Bicep, and replace the AI Search admin-key env var with a managed-identity data-plane call (or Key Vault reference).** (Effort M, high security ROI.)
6. **Close H6: add a project-local `Dockerfile`** and point `containerImage` at the ACR path `DEPLOY.md` already documents. (Effort S.)
7. **Close H7: deprecate or namespace `/arrangements/*`.** Pick the `/api/*` surface as canonical; keep `/arrangements/*` as an explicit legacy alias with a deprecation header, or remove. (Effort S.)
8. **Close H2 + M5 + M6 + M7 as a "production hardening" mini-workstream.** LLM-driven party/hallmark parsing, upload validation, retry/timeout policy, and domain telemetry events all sit in the service layer and can ship together. (Effort M.)
9. **Close M8: update the `.drawio` label set** (gpt-5.2, Key Vault node, Cosmos 4-container annotation) once C3 lands.

---

## 16. Files Reviewed

| File | Lines | Purpose |
|---|---:|---|
| [`src/mdr_agent/main.py`](../src/mdr_agent/main.py) | 335 | FastAPI app, all 12 domain routes, cached service singletons. |
| [`src/mdr_agent/models.py`](../src/mdr_agent/models.py) | 174 | Pydantic domain model (`MDRArrangement`, `Party`, `Hallmark`), API payloads, `MANDATORY_FIELDS`. |
| [`src/mdr_agent/config.py`](../src/mdr_agent/config.py) | 58 | Env-var-backed `Settings` dataclass; `azure_enabled` toggle. |
| [`src/mdr_agent/services/extraction_agent.py`](../src/mdr_agent/services/extraction_agent.py) | 162 | `HeuristicExtractionAgent` (regex) + `AzureOpenAIExtractionAgent` (JSON-object mode). |
| [`src/mdr_agent/services/chat_session.py`](../src/mdr_agent/services/chat_session.py) | 124 | HITL state machine; field-specific answer parsing. |
| [`src/mdr_agent/services/qa_service.py`](../src/mdr_agent/services/qa_service.py) | 197 | `LocalQAService` snippet KB + `AzureOpenAIQAService` with optional AI Search retrieval. |
| [`src/mdr_agent/services/document_ingestion.py`](../src/mdr_agent/services/document_ingestion.py) | 109 | `LocalDocumentIngestion` + `AzureDocumentIngestion` (Blob + Document Intelligence `prebuilt-layout`). |
| [`src/mdr_agent/services/guardrails.py`](../src/mdr_agent/services/guardrails.py) | 50 | Regex off-topic blocklist + compliance-hint allowlist. |
| [`src/mdr_agent/services/clarification_service.py`](../src/mdr_agent/services/clarification_service.py) | 68 | `MANDATORY_FIELDS` enforcement + canonical field questions. |
| [`src/mdr_agent/services/repository.py`](../src/mdr_agent/services/repository.py) | 137 | `InMemoryRepository` + `CosmosRepository` (arrangements + sessions containers only). |
| [`tests/test_generated_project.py`](../tests/test_generated_project.py) | 267 | 12 tests (layout, health, clarification, upload, HITL, Q&A, session lifecycle, off-topic, QA routing, case from text + confirm). |
| [`infra/main.bicep`](../infra/main.bicep) | 334 | Full topology: MI, KV, Log Analytics, App Insights, Storage (2 containers), Cosmos (4 containers), AI Search, OpenAI + deployment, Document Intelligence, Container Apps env + app, APIM. **No role assignments.** |
| [`diagrams/mdr-support-20260416174652.drawio`](../diagrams/mdr-support-20260416174652.drawio) | — | Spot-checked (node labels only; not modified). |
| [`docs/gap-analysis-crest-alpha-v2-preview-rerun-20260417.md`](./gap-analysis-crest-alpha-v2-preview-rerun-20260417.md) | — | Prior analysis — referenced for context only; this document is an independent read. |

---

## 17. Appendix A — Route Inventory (verbatim from `app.routes`)

```
/api/case/from-text
/api/case/{arrangement_id}
/api/case/{arrangement_id}/confirm
/api/chat
/api/session
/api/session/{session_id}
/api/upload
/arrangements/upload
/arrangements/{arrangement_id}
/arrangements/{arrangement_id}/chat
/arrangements/{arrangement_id}/clarifications
/arrangements/{arrangement_id}/draft
/docs
/docs/oauth2-redirect
/health
/openapi.json
/qa
/redoc
```

## 18. Appendix B — Diagram Node Inventory (verbatim labels)

```
MDR Arrangement Extraction Agent - Overview
Tax Analyst
Entra ID
API Management (JWT + Rate Limit)
MDR Agent API (Container Apps)
Azure OpenAI (gpt-4o)
Document Intelligence
Azure AI Search (optional RAG)
Blob Storage (uploaded docs)
Cosmos DB (drafts + sessions)
Managed Identity
App Insights + Log Analytics
```

Edge labels: `HTTPS`, `JWT validate`, `REST`, `extract`, `layout analyze`, `put blob`, `upsert draft / append chat turn`, `retrieve context (optional)`, `uses MI for all downstream calls`, `secrets`, `telemetry`.
