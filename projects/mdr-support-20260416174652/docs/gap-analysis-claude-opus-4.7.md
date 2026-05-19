# MDR Support — Gap Analysis

- **Project:** `mdr-support-20260416174652`
- **BRD source:** [`docs/intake/mdr-support.md`](../../../docs/intake/mdr-support.md)
- **Analysis date:** 2026-04-17
- **Analyst model:** Claude Opus 4.7 (GitHub Copilot)

## BRD coverage — solid vs missing

### ✅ Solid against the BRD
- **MDR-specific Q&A** — `POST /qa` + [`qa_service.py`](../src/mdr_agent/services/qa_service.py).
- **File-upload extraction flow** — `POST /arrangements/upload` + Blob + Document Intelligence `prebuilt-layout` in [`document_ingestion.py`](../src/mdr_agent/services/document_ingestion.py).
- **Structured JSON schema** — [`models.py::MDRArrangement`](../src/mdr_agent/models.py) is DAC6-aligned (parties with roles, hallmarks A–E, jurisdictions, main-benefit test, value/currency).
- **Human-in-the-loop chat + clarification loop** — state machine in [`chat_session.py`](../src/mdr_agent/services/chat_session.py), mandatory-field detector in [`clarification_service.py`](../src/mdr_agent/services/clarification_service.py).
- **Draft finalisation with gating** — `POST /arrangements/{id}/draft` returns 409 while mandatory fields are missing.
- **Local fallback paths** — every Azure service has a deterministic offline implementation so the team can iterate without credentials.
- **Batch explicitly deferred** — matches the BRD.
- **Infra breadth** — Container Apps + APIM + OpenAI + Doc Intelligence + Blob + Cosmos + Managed Identity + Key Vault + App Insights + Log Analytics.

---

## Gaps — ranked by severity

### 🔴 High (block production / BRD compliance)

| # | Gap | Why it matters | Where | Suggested fix |
|---|---|---|---|---|
| G1 | **No RBAC role assignments in Bicep** | [`DEPLOY.md`](../DEPLOY.md) tells operators to grant `Cognitive Services OpenAI User`, `Storage Blob Data Contributor`, `Cosmos DB Built-in Data Contributor`, etc., but [`main.bicep`](../infra/main.bicep) has zero `Microsoft.Authorization/roleAssignments`. With `disableLocalAuth=true` the Container App will 403 on every call until someone manually clicks through the portal. | `infra/main.bicep` | Add role-assignment resources on the MI principal id to: OpenAI (`5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`), Doc Intelligence (`a97b65f3-24c7-4388-baec-2e87135dc908`), Storage Blob (`ba92f5b4-2d11-453d-a403-e96b0029c9fe`), Cosmos SQL data role (via `Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments`), Key Vault Secrets User (`4633458b-17de-e7ea-6b7d-21b2a73e9e7b`), Monitoring Metrics Publisher. |
| G2 | **No authentication on the API** | BRD targets EY Tax staff; today `POST /arrangements/upload` and `POST /qa` are anonymous. Diagrams claim APIM does JWT, but APIM in the Bicep has no API, no product, no policies — the Container App is `external: true` with no auth in front of it. | `infra/main.bicep`, `src/mdr_agent/main.py` | Add `Microsoft.ApiManagement/service/apis` + `/policies` for `validate-jwt` against Entra ID; set Container App ingress to internal (or IP-restricted to APIM's outbound IPs). Add a FastAPI dependency that validates the `Authorization: Bearer` header as a belt-and-braces check. |
| G3 | **No Dockerfile** | Container App defaults to the Microsoft hello-world image (`containerImage` param default). There's no build recipe for the real `src/mdr_agent` code, so the deployed app cannot actually run. | project root | Add a `Dockerfile` (Python 3.11-slim, non-root user, `uvicorn mdr_agent.main:app --host 0.0.0.0 --port 8000`) + `.dockerignore`. Wire `az acr build` into `DEPLOY.md`. |
| G4 | **App Insights / OpenTelemetry not initialised in code** | `azure-monitor-opentelemetry` is a dependency and the connection string is injected, but nothing calls `configure_azure_monitor()`. No traces, no request telemetry, no dependency spans → BRD's "testable end-to-end flows" + operational observability is effectively missing in production. | `src/mdr_agent/main.py` | In a FastAPI lifespan handler, call `configure_azure_monitor(connection_string=settings.appinsights_connection_string)` when the env var is set; instrument FastAPI + requests. |

### 🟡 Medium (quality / BRD alignment, not blockers)

| # | Gap | Why it matters | Where | Suggested fix |
|---|---|---|---|---|
| G5 | **Chat answer parsing is crude** | `_apply_answer_to_arrangement` treats the whole `parties` answer as one `relevant_taxpayer` name. BRD wants the agent to *guide* users — a user answering *"Acme LuxCo (intermediary, LU); Acme IE (taxpayer, IE)"* gets a degraded structure. | [`chat_session.py`](../src/mdr_agent/services/chat_session.py) | Use the LLM as an answer-parser: a small extraction prompt per field that returns the typed sub-structure. Keep the regex path as a fallback. |
| G6 | **No PDF page cap / size limit** | `await file.read()` loads the whole upload into memory; a 500 MB PDF will OOM the 1 GiB container. Document Intelligence also has per-call page limits. | [`main.py`](../src/mdr_agent/main.py) | Enforce a `max_upload_mb` setting (default 20), reject larger payloads with 413, stream to blob instead of reading fully in-memory. |
| G7 | **No retry / backoff around Azure SDK calls** | OpenAI + Doc Intelligence throttle frequently; one 429 surfaces as a 500 to the user. | `extraction_agent.py`, `document_ingestion.py` | Wrap the SDK calls in `tenacity.retry` with exponential backoff on `RateLimitError` / `HttpResponseError`. |
| G8 | **Jurisdiction heuristic false-positives** | `HeuristicExtractionAgent` grabs any two-letter uppercase token as a jurisdiction — includes "MDR", "VAT", "EY", "IT". | [`extraction_agent.py`](../src/mdr_agent/services/extraction_agent.py) | Filter against a real ISO-3166 alpha-2 allowlist (e.g. the `iso3166` package or a frozenset literal). |
| G9 | **Cosmos `append_turn` uses timestamp as part of the id** | Two turns within the same millisecond collide (conflict) — unlikely but possible under burst. | [`repository.py`](../src/mdr_agent/services/repository.py) | Append a `uuid4().hex[:8]` to the id. |
| G10 | **No concurrency control on arrangement writes** | Two simultaneous chat turns against the same `arrangement_id` can race and one overwrites the other. | `repository.py::CosmosRepository.save` | Use Cosmos optimistic concurrency (`etag` + `if_match_etag`) on `upsert_item`, or serialize via a repository lock. |
| G11 | **No Key Vault secret wiring** | Key Vault is deployed but nothing uses it — no third-party secrets, no APIM subscription key, no signing key. | `infra/main.bicep`, `src/mdr_agent/config.py` | Either remove Key Vault (YAGNI) or add a `secretRef` block in the Container App for at least one real secret (e.g. an APIM gateway key for upstream calls). |
| G12 | **Audit log missing** | Tax compliance workloads usually require an immutable audit of who asked what and when. Chat turns land in Cosmos but extraction outcomes + user identity don't. | new service | Add an append-only `audit` Cosmos container or stream to Log Analytics custom table: `{user_oid, arrangement_id, action, model, timestamp, confidence}`. |

### 🟢 Low (polish / dev-experience)

| # | Gap | Suggested fix |
|---|---|---|
| G13 | `UploadResponse` model defined but unused — `upload_document` returns `ExtractionResult` instead. | Delete `UploadResponse` or switch one of the two consumers. |
| G14 | No OpenAPI tags / response examples. | Add `tags=["arrangements"]` / `tags=["qa"]` and `response_model_exclude_none=True`. |
| G15 | Tests are all in one file and all happy-path. | Split into `test_extraction.py`, `test_chat_session.py`, `test_qa.py`; add failure cases (malformed JSON from LLM, blob upload failure, Cosmos 429). |
| G16 | No CORS middleware — browser clients can't call the API from a different origin. | Add `CORSMiddleware` with an env-driven allowlist. |
| G17 | `SYSTEM_PROMPT` is inline in code — changing it requires a deploy. | Move to `prompts/mdr_extraction_v1.md` and load at import time; include a version in the response. |
| G18 | APIM is `Developer` SKU (no SLA, single region). | Fine for Phase 1; add a `skuName` parameter and flag `Standard/Premium` as the prod path in `DEPLOY.md`. |
| G19 | No `/ready` endpoint separate from `/health`. | Add a readiness probe that actually pings OpenAI / Cosmos. |
| G20 | Traceability matrix has no test IDs mapped per requirement. | Extend columns: `| REQ | … | Test(s) |`. |

---

## Recommended next iteration (ordered)

1. **G3** Dockerfile + `.dockerignore` — unblocks deploy.
2. **G1** RBAC role assignments in Bicep — unblocks runtime.
3. **G4** Wire `configure_azure_monitor()` in a FastAPI lifespan handler.
4. **G2** APIM API + `validate-jwt` policy + make Container App ingress internal.
5. **G6** Upload size cap + streaming.
6. **G5** LLM-backed answer parser for structured fields.
7. **G7** Retry/backoff around OpenAI + Doc Intelligence.
8. **G12** Audit log.
