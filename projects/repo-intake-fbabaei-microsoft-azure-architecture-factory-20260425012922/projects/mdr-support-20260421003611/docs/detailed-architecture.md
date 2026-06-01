# Mdr Support -- Detailed Architecture (extraction-chat, .NET)

## Service boundaries

| Class | Responsibility | Replace with |
|---|---|---|
| `Services/DocumentIngestionService.cs` | Parse uploaded bytes into a text excerpt. | Azure AI Document Intelligence |
| `Services/ExtractionService.cs` | Extract structured fields from the excerpt. | Azure OpenAI / Foundry agent with JSON mode |
| `Services/ClarificationService.cs` | Compute the next missing mandatory field. | Keep deterministic; feed prompts into chat UX. |
| `Services/DraftRepository.cs` | Persist drafts across chat turns. | Cosmos DB / Azure SQL |
| `Services/SessionService.cs` | Track human-in-the-loop conversation history. | Cosmos DB / App Insights custom events |

## Data flow

1. `POST /documents/upload` -> `DocumentIngestionService` -> `ExtractionService` -> persist draft + clarifications.
2. UI polls `GET /documents/{id}/clarifications` and asks the user the next question.
3. Answer posted to `POST /documents/{id}/chat` -> field merged into draft -> clarifications recomputed.
4. Once clarifications is empty, `POST /documents/{id}/draft` finalizes the arrangement.

## Azure mapping (suggested)

- Container Apps or App Service for the ASP.NET Core process (port 8080; `/health` + `/health/ready`).
- Azure Blob Storage for the raw uploads; `DraftRepository` swaps to Cosmos DB / Azure SQL.
- Azure OpenAI or Azure AI Foundry Agent Service for extraction + clarification.
- `DefaultAzureCredential` + Managed Identity for all Azure SDK clients.
- Application Insights + Log Analytics when `enableObservability` is true.
