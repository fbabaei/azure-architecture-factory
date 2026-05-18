# MDR Support - Detailed Architecture Diagram Notes

Three-tab draw.io file rendered with Azure stencils (`mxgraph.azure.*`).

## Tab 1 - Logical Architecture
Swimlanes: **Clients, Identity, API Gateway, MDR Agent Service, AI Services,
Data, Security / Observability**.

- **Clients**: Tax Analyst browser and future workflow/API clients.
- **Identity**: Entra ID for user JWTs and user-assigned Managed Identity for the app.
- **API Gateway**: API Management (JWT validation + rate limits).
- **MDR Agent Service**: Container Apps-hosted FastAPI app, image pulled from a
  co-provisioned **Azure Container Registry (ACR)** via managed identity (AcrPull).
  Internal components:
  - **Chat Agent** (user-facing orchestrator) with a 3-layer **Off-topic Guardrail**
    (system prompt + intent classifier + keyword blocklist).
  - **Extraction Agent** with **Structured Output + Pydantic Validator** to enforce
    `MDRArrangement` schema conformance.
  - Upload handler, clarification engine, session/case repository, chat session state machine.
- **AI Services**:
  - **Azure OpenAI** (`gpt-5.2` chat + `text-embedding-3-small`).
  - **Document Intelligence** (`prebuilt-layout`) \u2014 Phase 1 substitute for the optional
    Azure AI Content Understanding / GPT-5.2 vision path.
  - **Azure AI Search** for **hybrid RAG** (vector + keyword + semantic reranking).
- **Data**: Blob Storage (`mdr-documents` for uploads, `knowledge-base-source` for RAG)
  plus four Cosmos DB containers (`arrangements`, `sessions`, `case-drafts`, `audit-log`).
- **Security / Observability**: Key Vault, App Insights, Log Analytics, Azure Monitor.

Edge highlights:
- APIM -> API route and policy enforcement.
- ACR -> API image pull (AcrPull via MI).
- API -> Document Intelligence (PDF layout extraction).
- API -> OpenAI (structured extraction, Q&A generation, embeddings).
- API -> AI Search (hybrid vector + semantic retrieval context for Q&A).
- API -> Blob Storage (`mdr-documents` source uploads, `knowledge-base-source` KB ingest).
- API <-> Cosmos (`arrangements`, `sessions`, `case-drafts`, `audit-log`).
- API -> App Insights (telemetry, traces, and metrics).

## Tab 2 - Key Flows
Three horizontal flow lanes:
1. **Flow A: File Upload - Extraction**
   (Client -> APIM -> MDR Agent -> Blob -> Document Intelligence -> OpenAI -> Cosmos -> response).
2. **Flow B: Session and Clarification Chat**
   (`POST /api/session`, `POST /api/chat`, retrieval of missing fields, iterative updates).
3. **Flow C: Case Lifecycle and Finalisation**
   (`POST /api/case/from-text`, `GET/PUT /api/case/{id}`, `POST /api/case/{id}/confirm`).

## Hybrid RAG Bootstrap
- Run `scripts/bootstrap_search_index.py` after deployment to create the `contentVector`
  field, semantic configuration, and seed MDR reference content.

## Tab 3 - Security and Governance
- Azure Policy intent: enforce managed identity and disable key-based/local auth where supported.
- RBAC assignments on the user-assigned managed identity include:
  - Cognitive Services OpenAI User -> Azure OpenAI
  - Cognitive Services User -> Document Intelligence
  - Search Index Data Reader (or equivalent) -> Azure AI Search
  - Storage Blob Data Contributor -> Blob Storage
  - Cosmos DB Built-in Data Contributor -> Cosmos DB (data plane, via `sqlRoleAssignments`)
  - Key Vault Secrets User -> Key Vault
  - AcrPull -> Azure Container Registry
  - Monitoring Metrics Publisher -> Application Insights
- Governance notes: environment-specific resource groups, required tags,
  restricted blob public access, Key Vault RBAC mode, centralized monitoring.
- Phase 1 remains public-network oriented; Phase 2 target is VNet-integrated
  Container Apps with private endpoints for data and AI services.

## Related files
- Draw.io: `mdr-support-20260416174652-detailed-architecture.drawio`
- Overview diagram: `mdr-support-20260416174652.drawio`
- Document: `../docs/detailed-architecture.md`
