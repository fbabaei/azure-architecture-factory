flowchart TB
    subgraph Clients
        Web[Web Chat Client]
        Teams[Teams / M365 Bot]
    end

    subgraph ContainerApps[Azure Container Apps]
        API[casewright-api\nFastAPI]
        Worker[casewright-worker\nSB consumer]
    end

    Sched[casewright-scheduler\nFunctions: Timer + HTTP]

    subgraph Data
        Search[(Azure AI Search\nvector + semantic)]
        Blob[(Blob Storage)]
        Cosmos[(Cosmos DB\nhistory + sync-state)]
        SB[[Service Bus queue]]
    end

    OpenAI[[Azure OpenAI\nchat + embeddings]]
    Graph[(Microsoft Graph\nSharePoint)]
    Foundry[[Foundry prompt-agent\noptional]]

    Web -->|/api/chat| API
    Teams -->|/api/chat| API
    API -->|hybrid query + rerank| Search
    API -->|grounded answer| Foundry
    API -->|fallback| OpenAI
    API -->|history| Cosmos
    API -->|enqueue sync| SB
    Sched -->|timer/http enqueue| SB
    SB --> Worker
    Worker -->|delta detect| Graph
    Worker -->|upload changed| Blob
    Worker -->|sync state| Cosmos
    Worker -->|run if changes>0| Search
    Search -->|pull + skillset| Blob
    Search -->|embeddings| OpenAI