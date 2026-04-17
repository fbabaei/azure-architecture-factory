# MDR Arrangement Extraction Agent - Detailed Architecture

This architecture is aligned with the Compliance Intelligence Agent target
design: a user-facing Chat Agent orchestrating specialist extraction,
schema-safe output, and a human-in-the-loop completion cycle.

## Component Inventory

### Clients
- **Tax analyst (browser)** - uploads arrangement PDFs, drives the
  clarification chat.
- **MDR workflow service** - future caller for system-to-system
  integration via APIM subscription.

### API Tier
- **Azure API Management** - public gateway, JWT validation against
  Entra ID, per-subscription rate limits.

### Compute
- **Container Apps environment** (`mdr-support-<env>-cae`).
- **MDR Agent Container App** (`mdr-support-<env>-api`) running
  FastAPI from `src/mdr_agent/main.py`. Key endpoints:
  - `POST /api/session` - create a conversation session.
  - `GET /api/session/{id}` - session history + current draft state.
  - `DELETE /api/session/{id}` - clear session and draft data.
  - `POST /api/chat` - intent-routed chat endpoint (Q&A, follow-up,
    off-topic guardrail).
  - `POST /api/upload` - upload a document and trigger extraction
    (alias to arrangement upload).
  - `POST /api/case/from-text` - create a draft from free-text input.
  - `GET /api/case/{id}` / `PUT /api/case/{id}` /
    `POST /api/case/{id}/confirm` - case retrieval, user edits, finalization.
  - `POST /arrangements/upload` - accept a file, persist to Blob,
    run Document Intelligence, call OpenAI, save draft.
  - `POST /arrangements/{id}/chat` - apply user answer, re-run
    clarification, return next question or completion reply.
  - `GET /arrangements/{id}` / `GET /arrangements/{id}/clarifications`.
  - `POST /arrangements/{id}/draft` - finalise when no clarifications
    remain.

### AI Services
- **Azure OpenAI** (`gpt-4o` by default; GPT-5.2-ready via deployment config)
  - structured JSON extraction from raw text and conversational response
  generation. Prompt lives in `src/mdr_agent/services/extraction_agent.py`.
- **Azure AI Document Intelligence** - `prebuilt-layout` model for
  PDF layout extraction.
- **Azure AI Search** - optional retrieval for compliance knowledge grounding
  in Q&A and jurisdiction-specific context.

### Data
- **Azure Blob Storage** (container: `mdr-documents`) - original
  uploaded PDFs / text files, partitioned by `arrangement_id`.
- **Azure Blob Storage** (container: `knowledge-base-source`) - source files
  for compliance RAG indexing.
- **Azure Cosmos DB (serverless)**
  - `arrangements` container - current `MDRArrangement` draft, keyed by
    `id` (= `arrangement_id`).
  - `sessions` container - append-only `ChatTurn` log, partitioned by
    `arrangement_id`.
  - `audit-log` container - immutable operational events.

### Security
- **User-assigned Managed Identity** - attached to the Container App;
  used for every downstream Azure call.
- **Azure Key Vault** - holds any third-party secrets
  (RBAC-authorised, no access policies).
- **Entra ID** - issues access tokens for tax analysts; APIM validates
  the JWT before routing.

### Observability
- **Application Insights** - request / dependency telemetry from the
  Container App via `azure-monitor-opentelemetry`.
- **Log Analytics workspace** - Container Apps stdout/stderr logs.
- **Azure Monitor Action Group** - optional email alerting.

## Key Flows

### Flow A - File upload extraction
1. Analyst uploads a PDF to `POST /arrangements/upload` through APIM.
2. Container App persists the bytes in Blob Storage under
   `{arrangement_id}/{filename}`.
3. Document Intelligence `prebuilt-layout` returns pages + lines.
4. Azure OpenAI (`gpt-4o`) returns a strict JSON MDR arrangement.
5. Draft is upserted into Cosmos `arrangements`.
6. Response includes the `arrangement_id`, confidence, and model used.

### Flow A2 - Text prompt to draft
1. Analyst submits free text to `POST /api/case/from-text`.
2. Extraction Agent produces partial structured arrangement.
3. Clarification service identifies missing required fields.
4. Chat Agent requests missing values until the user confirms finalization.

### Flow B - Human-in-the-loop chat
1. Client polls `GET /arrangements/{id}/clarifications` and receives the
   next `ClarificationQuestion` for the first missing mandatory field.
2. Client posts the user's answer to `POST /arrangements/{id}/chat`.
3. `chat_session.handle_chat_turn` merges the answer into the draft,
   upserts to Cosmos, appends both the user turn and assistant reply to
   the `sessions` container, then returns the next question (or a
   completion reply).
4. Loop until `clarifications.is_complete == true`.

### Flow C - Arrangement draft finalisation
1. Client calls `POST /arrangements/{id}/draft`.
2. Service re-validates that no mandatory fields are missing; if any
   are, returns HTTP 409 with the missing list.
3. On success the service returns the canonical JSON arrangement for
   downstream use.

### Flow D - Compliance Q&A (RAG-ready)
1. User sends a question to `POST /api/chat`.
2. Off-topic guardrail evaluates compliance relevance.
3. If in-scope, the Q&A service answers with MDR/DAC6 guidance and can
  attach retrieval snippets from a configured knowledge base.
4. If out-of-scope, the API returns a polite refusal message.

## Source Code Map
- API service: `src/mdr_agent/main.py`.
- Domain model + mandatory field list: `src/mdr_agent/models.py`.
- Extraction agent (Azure OpenAI + heuristic fallback): `src/mdr_agent/services/extraction_agent.py`.
- Document ingestion (Blob + Document Intelligence): `src/mdr_agent/services/document_ingestion.py`.
- Clarification engine: `src/mdr_agent/services/clarification_service.py`.
- Chat state machine: `src/mdr_agent/services/chat_session.py`.
- Persistence (Cosmos + in-memory): `src/mdr_agent/services/repository.py`.
- Off-topic guardrail: `src/mdr_agent/services/guardrails.py`.
- Configuration: `src/mdr_agent/config.py`.

## Infrastructure Map
- `infra/main.bicep` provisions all services above.
- Identity / secret RBAC wiring is listed in `DEPLOY.md`.

## Out of Scope (Phase 1)
- Batch / multi-arrangement processing.
- Production-grade network isolation (VNet integration, private
  endpoints) - to be added in Phase 2.
- Human approval + sign-off workflow for generated drafts.
