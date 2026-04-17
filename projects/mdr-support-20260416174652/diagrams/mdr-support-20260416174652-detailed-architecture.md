# MDR Support - Detailed Architecture Diagram Notes

Three-tab draw.io file rendered with Azure stencils (`mxgraph.azure.*`).

## Tab 1 - Logical Architecture
Swimlanes: **Clients, Identity, API Gateway, MDR Agent Service, AI Services,
Data, Security / Observability**.

- **Clients**: Tax Analyst browser and future workflow/API clients.
- **Identity**: Entra ID for user JWTs and user-assigned Managed Identity for the app.
- **API Gateway**: API Management (JWT validation + rate limits).
- **MDR Agent Service**: Container Apps-hosted FastAPI app.
  Internal capabilities: upload ingestion, extraction agent, clarification engine,
  session/case repository, chat router with `qa` / `clarification` / `off_topic` modes.
- **AI Services**: Azure OpenAI (`gpt-4o`), Document Intelligence, and optional Azure AI Search retrieval.
- **Data**: Blob Storage plus Cosmos DB containers for session/case data
  (`arrangements`, `sessions`, `case-drafts`, `audit-log`).
- **Security / Observability**: Key Vault, App Insights, Log Analytics, Azure Monitor.

Edge highlights:
- APIM -> API route and policy enforcement.
- API -> Document Intelligence (PDF layout extraction).
- API -> OpenAI (structured extraction + Q&A generation).
- API -> AI Search (optional retrieval context for Q&A).
- API -> Blob Storage (raw source and knowledge-base documents).
- API <-> Cosmos (session/case state, draft updates, turn history, audit trail).
- API -> App Insights (telemetry, traces, and metrics).

## Tab 2 - Key Flows
Three horizontal flow lanes:
1. **Flow A: File Upload - Extraction**
   (Client -> APIM -> MDR Agent -> Blob -> Document Intelligence -> OpenAI -> Cosmos -> response).
2. **Flow B: Session and Clarification Chat**
   (`POST /api/session`, `POST /api/chat`, retrieval of missing fields, iterative updates).
3. **Flow C: Case Lifecycle and Finalisation**
   (`POST /api/case/from-text`, `GET/PUT /api/case/{id}`, `POST /api/case/{id}/confirm`).

## Tab 3 - Security and Governance
- Azure Policy intent: enforce managed identity and disable key-based/local auth where supported.
- RBAC assignments on the user-assigned managed identity include:
  - Cognitive Services OpenAI User -> Azure OpenAI
  - Cognitive Services User -> Document Intelligence
  - Search Index Data Reader (or equivalent) -> Azure AI Search
  - Storage Blob Data Contributor -> Blob Storage
  - Cosmos DB Built-in Data Contributor -> Cosmos DB
  - Key Vault Secrets User -> Key Vault
  - Monitoring Metrics Publisher -> Application Insights
- Governance notes: environment-specific resource groups, required tags,
  restricted blob public access, Key Vault RBAC mode, centralized monitoring.
- Phase 1 remains public-network oriented; Phase 2 target is VNet-integrated
  Container Apps with private endpoints for data and AI services.

## Related files
- Draw.io: `mdr-support-20260416174652-detailed-architecture.drawio`
- Overview diagram: `mdr-support-20260416174652.drawio`
- Document: `../docs/detailed-architecture.md`
