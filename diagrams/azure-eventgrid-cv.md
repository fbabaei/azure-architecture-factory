# Azure Event Grid → Functions → Computer Vision → Cosmos DB

```mermaid
flowchart TD
  storage[centralstorage\n(Storage Account)] -->|event: blob created| grid1[Grid1\n(Event Grid)]
  grid1 --> functions[Azure Functions\n(event handlers)]
  functions --> cv[Computer Vision\n(Cognitive Services API)]
  cv --> cosmos[Cosmos DB\n(results store)]

  classDef azure fill:#f0f8ff,stroke:#2b7ce9;
  class storage azure;
  class grid1 fill:#fff8e6,stroke:#e67e22;
  class functions fill:#f0fff0,stroke:#2e8b57;
  class cv fill:#fff0f8,stroke:#c2185b;
  class cosmos fill:#f7fff7,stroke:#16a085;
```

**Flow**
- `centralstorage` (Storage Account) publishes blob-created events to `Grid1` (Event Grid).
- `Grid1` routes events to Azure Functions which execute business logic.
- Azure Functions call the Computer Vision API (Cognitive Services) to analyze images.
- Analysis results are persisted to Azure Cosmos DB for downstream querying and reporting.

**Notes / Implementation tips**
- Use Event Grid subscription filtering to only forward relevant blob events to `Grid1`.
- Implement Functions with a retry policy and dead-lettering (e.g., storage queue or DLQ) for failed analyses.
- Secure calls to Computer Vision with managed identity or API keys stored in Key Vault.
- Use Cosmos DB partitioning and RU planning based on result volume.

File created: diagrams/azure-eventgrid-cv.md
