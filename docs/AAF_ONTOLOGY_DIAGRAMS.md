# AAF Ontology — Mermaid Diagrams

## Diagram 1 — Multi-Agent Architecture: Where Ontology Sits

```mermaid
graph TD
    User["👤 User / CSA / Portal"]
    Orchestrator["🧠 AAF Orchestrator\n(Parent Agent)"]

    subgraph Agents["Specialized Agents"]
        A1["📥 Intake /\nRequirement Normalizer"]
        A2["🔍 Pattern\nSelection"]
        A3["🏗️ Design /\nArchitecture Generation"]
        A4["✅ Validation /\nGovernance"]
        A5["📄 Documentation"]
        A6["⚙️ IaC /\nProvisioning"]
        A7["📡 Observability /\nOperations"]
        A8["🐙 GitHub-AAF\nPipeline Agent"]
    end

    subgraph SharedContext["Shared Context Layer"]
        Ontology["🗂️ Ontology\n(Semantic Backbone)\nEntities · Relationships · Rules"]
    end

    subgraph KnowledgeLayer["Knowledge Layer"]
        RAG["📚 RAG / Document Store\n(Standards, Examples,\nDesign Guides, Playbooks)"]
        Templates["📋 Templates &\nDocument Stores"]
    end

    subgraph ToolLayer["Tool Layer"]
        Tools["🔧 Tools / APIs\n(Deployment · Validation\nOpenAPI / MCP · Runtime)"]
        GitHubMCP["🐙 GitHub MCP Server\n(get_issue · create_branch\npush_files · create_pull_request\nadd_issue_comment)"]
        AAFMCP["🔌 AAF MCP Server\n(submit_brd · get_project_status\nget_project_artifacts · invoke_agent\nlist_projects)"]
    end

    User --> Orchestrator
    Orchestrator --> A1
    Orchestrator --> A2
    Orchestrator --> A3
    Orchestrator --> A4
    Orchestrator --> A5
    Orchestrator --> A6
    Orchestrator --> A7

    A1 -->|HIGH| Ontology
    A2 -->|VERY HIGH| Ontology
    A3 -->|VERY HIGH| Ontology
    A4 -->|EXTREMELY HIGH| Ontology
    A7 -->|HIGH| Ontology
    A5 -.->|MEDIUM| Ontology
    A6 -.->|MEDIUM| Ontology
    A8 -.->|LOW| Ontology

    A5 --> RAG
    A5 --> Templates
    A4 --> Tools
    A6 --> Tools
    A8 --> GitHubMCP
    A8 --> AAFMCP

    classDef agentBox fill:#0078d4,color:#fff,stroke:#005a9e
    classDef ontoBox fill:#107c10,color:#fff,stroke:#004b00
    classDef ragBox fill:#8764b8,color:#fff,stroke:#5c2d91
    classDef toolBox fill:#d83b01,color:#fff,stroke:#a80000
    classDef mcpBox fill:#e3008c,color:#fff,stroke:#a40062
    classDef userBox fill:#323130,color:#fff,stroke:#000
    classDef orchBox fill:#004e8c,color:#fff,stroke:#003966

    class A1,A2,A3,A4,A5,A6,A7,A8 agentBox
    class Ontology ontoBox
    class RAG,Templates ragBox
    class Tools toolBox
    class GitHubMCP,AAFMCP mcpBox
    class User userBox
    class Orchestrator orchBox
```

---

## Diagram 2 — Core Ontology Entity Model (Phase 1: Six-Domain Starter)

```mermaid
classDiagram
    class Requirement {
        +id : string
        +description : string
        +source : string
        +priority : High|Med|Low
    }
    class Constraint {
        +id : string
        +description : string
        +category : Regional|Security|Cost|Compliance
    }
    class Pattern {
        +id : string
        +name : string
        +category : string
        +tradeoffs : string[]
    }
    class AzureService {
        +id : string
        +name : string
        +tier : string
        +wafPillars : string[]
    }
    class Decision {
        +id : string
        +rationale : string
        +date : date
        +status : Proposed|Accepted|Superseded
    }
    class Artifact {
        +id : string
        +type : PRD|ADR|DiagramNotes|TestPlan|ObsPlan
        +version : string
        +url : string
    }

    class MCPTool {
        +id : string
        +server : GitHubMCP|AAFMCP
        +name : string
        +description : string
    }

    Requirement --> Constraint : hasConstraint
    Requirement --> Pattern : satisfiedBy
    Constraint --> Pattern : limits
    Pattern --> AzureService : implementedBy
    Decision --> Pattern : selects
    Decision --> AzureService : selects
    Artifact --> Decision : documents
    Artifact --> Requirement : traces
    MCPTool --> Artifact : produces
    MCPTool --> Requirement : ingests
```

---

## Diagram 3 — Extended Ontology Entity Model (Full Domain)

```mermaid
classDiagram
    class CustomerScenario {
        +id : string
        +name : string
        +industry : string
    }
    class BusinessGoal {
        +id : string
        +description : string
        +priority : string
    }
    class Requirement {
        +id : string
        +type : Functional|NFR|Security|Compliance
        +description : string
    }
    class NonFunctionalRequirement {
        +id : string
        +quality : Availability|Perf|Scalability|Reliability
        +target : string
    }
    class Constraint {
        +id : string
        +category : Regional|Cost|Compliance|Policy
    }
    class SecurityControl {
        +id : string
        +name : string
        +type : CMK|RBAC|PrivateEndpoint|ManagedIdentity
    }
    class Pattern {
        +id : string
        +name : string
        +category : EventDriven|MultiRegion|Serverless
    }
    class AzureService {
        +id : string
        +name : string
        +resourceType : string
    }
    class ArchitectureOption {
        +id : string
        +name : string
        +rationale : string
    }
    class Risk {
        +id : string
        +severity : Critical|High|Med|Low
        +description : string
    }
    class Decision {
        +id : string
        +rationale : string
        +status : Proposed|Accepted|Superseded
    }
    class Artifact {
        +type : PRD|ADR|DiagramNotes|TestPlan|ObsPlan
    }
    class Workload {
        +id : string
        +name : string
        +tier : Frontend|Backend|Data|Integration
    }
    class DeploymentTarget {
        +id : string
        +environment : Dev|Test|Prod
        +region : string
    }
    class Integration {
        +id : string
        +protocol : REST|AMQP|gRPC|Event
        +authPattern : string
    }
    class ExternalTrigger {
        +id : string
        +source : GitHubIssue|GitHubPR|Webhook|Label
        +payload : string
    }
    class MCPTool {
        +id : string
        +server : GitHubMCP|AAFMCP
        +name : string
        +description : string
    }

    CustomerScenario --> BusinessGoal : has
    BusinessGoal --> Requirement : requires
    Requirement --> Constraint : hasConstraint
    NonFunctionalRequirement --|> Requirement
    NonFunctionalRequirement --> Pattern : drives
    Pattern --> AzureService : implementedBy
    ArchitectureOption --> AzureService : uses
    ArchitectureOption --> Pattern : appliesPattern
    ArchitectureOption --> Risk : mitigates
    Constraint --> ArchitectureOption : limits
    Decision --> ArchitectureOption : selects
    Artifact --> Decision : documents
    Artifact --> Requirement : traces
    Workload --> SecurityControl : requires
    Workload --> Integration : exposes
    DeploymentTarget --> AzureService : hosts
    DeploymentTarget --> Workload : runs
    ExternalTrigger --> Requirement : spawns
    MCPTool --> ExternalTrigger : reads
    MCPTool --> Artifact : pushes
```

---

## Diagram 4 — Requirement → Architecture Traceability Flow

```mermaid
flowchart LR
    Input(["📝 Raw User Input\n'Secure multi-region\ndocument processing\nwith CMK + auditability'"])

    subgraph Phase1["Phase 1 · Intake Agent (High ontology)"]
        BG["BusinessGoal:\nDocument Processing"]
        C["Constraint:\nMulti-Region"]
        SC["SecurityControl:\nCMK"]
        NFR["NFR:\nAuditability"]
    end

    subgraph Phase2["Phase 2 · Pattern Selection Agent (Very High ontology)"]
        P1["Pattern:\nEvent-Driven Processing"]
        P2["Pattern:\nMulti-Region Active-Active"]
        AS1["AzureService:\nAzure Storage"]
        AS2["AzureService:\nCosmos DB (multi-region)"]
        AS3["AzureService:\nKey Vault (CMK)"]
        AS4["AzureService:\nAzure Monitor + Log Analytics"]
    end

    subgraph Phase3["Phase 3 · Design Agent (Very High ontology)"]
        AO["ArchitectureOption:\nEvent-Driven Multi-Region\nDocument Platform"]
    end

    subgraph Phase4["Phase 4 · Validation Agent (Extremely High ontology)"]
        V1{"Every NFR\nsatisfied?"}
        V2{"Every external\nintegration has auth?"}
        V3{"Observability\nmapped?"}
    end

    subgraph Phase5["Phase 5 · Artifacts"]
        D["Decision: Accepted"]
        A1["Artifact: ADR"]
        A2["Artifact: PRD"]
        A3["Artifact: Diagram"]
    end

    Input --> BG & C & SC & NFR

    BG --> P1
    C  --> P2
    SC --> AS3
    NFR --> AS4
    P1 --> AS1 & AS2
    P2 --> AS2

    P1 & P2 & AS1 & AS2 & AS3 & AS4 --> AO

    AO --> V1 & V2 & V3
    V1 & V2 & V3 --> D
    D --> A1 & A2 & A3
```

---

## Diagram 5 — Ontology Usage Heat Map by Agent Role

```mermaid
graph TB
    subgraph EH["🔴 EXTREMELY HIGH"]
        AG4["Validation / Governance Agent\n▸ NFR coverage rules\n▸ auth-on-every-integration rule\n▸ observability completeness rule\n▸ identity pattern rule"]
    end
    subgraph VH["🟠 VERY HIGH"]
        AG2["Pattern Selection Agent\n▸ pattern catalog\n▸ service compatibility\n▸ tradeoff graph"]
        AG3["Design / Architecture Generation Agent\n▸ component validity\n▸ dependency constraints\n▸ WAF alignment"]
    end
    subgraph HH["🟡 HIGH"]
        AG1["Intake / Requirement Normalizer\n▸ entity extraction\n▸ goal / constraint / NFR typing"]
        AG7["Observability / Operations Agent\n▸ workload → service → signal mapping\n▸ dependency graph"]
    end
    subgraph MH["🟢 MEDIUM — ontology + RAG"]
        AG5["Documentation Agent\n▸ structured facts from ontology\n▸ prose from RAG + templates"]
        AG6["IaC / Provisioning Agent\n▸ service/resource mapping\n▸ implementation from repos/templates"]
    end
    subgraph LW["⚪ LOW — MCP orchestration"]
        AG8["GitHub-AAF Pipeline Agent\n▸ bridges GitHub issues → AAF BRDs\n▸ pushes artifacts to GitHub\n▸ routes to specialist agents via AAF MCP"]
    end

    Ontology(["🗂️ Shared\nOntology\nLayer"])

    AG4 -->|rules + validation| Ontology
    AG2 -->|pattern traversal| Ontology
    AG3 -->|component + constraint query| Ontology
    AG1 -->|entity population| Ontology
    AG7 -->|dependency + signal query| Ontology
    AG5 -.->|structured facts| Ontology
    AG6 -.->|service metadata| Ontology
    AG8 -.->|project slug lookup| Ontology
```

---

## Diagram 6 — What Belongs Where (Ontology vs RAG vs Tools)

```mermaid
graph TD
    subgraph Ontology["🗂️ Ontology\n(Meaning · Relationships · Rules)"]
        O1["Architecture entity types"]
        O2["Service capabilities & constraints"]
        O3["Pattern ↔ service mappings"]
        O4["NFR → pattern rules"]
        O5["Governance / validation rules"]
        O6["Requirement ↔ decision traceability"]
    end

    subgraph RAG["📚 RAG / Document Layer\n(Explanatory Content · Examples)"]
        R1["Long-form design guides"]
        R2["Internal architecture standards"]
        R3["Workshop recordings / transcripts"]
        R4["Implementation playbooks"]
        R5["Reference architecture examples"]
        R6["Discovery documents"]
    end

    subgraph Tools["🔧 Tool Layer\n(Actions · Runtime)"]
        T1["Bicep / Terraform generation"]
        T2["Deployment execution"]
        T3["Compliance validation APIs"]
        T4["OpenAPI / MCP integrations"]
        T5["Cost estimation APIs"]
        T6["Runtime health checks"]
        T7["GitHub MCP tools\n(get_issue · create_branch\npush_files · create_pull_request)"]
        T8["AAF MCP tools\n(submit_brd · invoke_agent\nget_project_artifacts · list_projects)"]
    end

    Orchestrator["🧠 AAF Orchestrator"] --> Ontology
    Orchestrator --> RAG
    Orchestrator --> Tools
```

---

> **One-sentence framing:**  
> *"In AAF, ontology is the shared architecture knowledge model that lets every agent interpret requirements, patterns, services, and decisions consistently, while RAG and tools handle unstructured guidance and execution."*
