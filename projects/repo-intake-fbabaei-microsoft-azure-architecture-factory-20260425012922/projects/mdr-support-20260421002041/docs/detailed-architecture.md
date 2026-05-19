# Mdr Support -- Detailed Architecture (extraction-chat)

## Service boundaries

| Module | Responsibility | Replace with |
|---|---|---|
| `src/mdr_support/services/document_ingestion.py` | Parse uploaded bytes into a text excerpt. | Azure AI Document Intelligence |
| `src/mdr_support/services/extraction_service.py` | Extract structured fields from the excerpt. | Azure OpenAI / Foundry agent with JSON mode |
| `src/mdr_support/services/clarification_service.py` | Compute the next missing mandatory field. | Keep deterministic; feed prompts into chat UX. |
| `src/mdr_support/services/repository.py` | Persist drafts across chat turns. | Cosmos DB / Azure SQL |
| `src/mdr_support/services/session_service.py` | Track human-in-the-loop conversation history. | Cosmos DB / App Insights custom events |

## Data flow

1. `POST /documents/upload` -> ingestion -> extraction -> persist draft + clarifications.
2. UI polls `GET /documents/{id}/clarifications` and asks the next question.
3. Answers posted to `POST /documents/{id}/chat` merge into the draft; clarifications recomputed.
4. `POST /documents/{id}/draft` finalizes when clarifications is empty.

## Azure mapping (suggested)

- Container Apps / App Service for FastAPI (`/health` probe on port 8000).
- Blob Storage for raw uploads; Cosmos DB / Azure SQL for drafts.
- Azure OpenAI or Azure AI Foundry Agent Service for extraction + clarification.
- Application Insights + Log Analytics for telemetry.
