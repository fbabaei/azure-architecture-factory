# Product Requirements Document (PRD)
## Azure Architecture Factory

**Version:** 2.0  
**Date:** March 19, 2026  
**Status:** Complete & Production-Ready

---

## 1. Executive Summary

The **Azure Architecture Factory** is an AI-driven platform that automates the full project lifecycle — from business requirements to deployed Azure infrastructure — using a fleet of 8 custom Copilot agents. The factory generates architecture diagrams, scaffolds modular Python microservices, produces Bicep infrastructure-as-code, auto-validates and self-heals IaC errors, reviews production readiness, and deploys to Azure — all orchestrated in a single command.

The platform includes a **reference implementation**: a production-grade Fabric Medallion data pipeline (Bronze/Silver/Gold layers) with real-time connectors to Azure services, structured observability, enterprise-grade resilience, and pluggable governance.

**Key Innovation:** Combines AI-driven agent orchestration with architecture diagram generation (via MCP Draw.io), automatic code scaffolding, self-healing Bicep validation, and one-command Azure deployment — enabling teams to go from a BRD to a deployed project in hours instead of weeks.

---

## 2. Product Vision

### Mission
Enable engineering teams to rapidly convert business requirements into production-ready Azure projects — with AI agents handling architecture design, code scaffolding, infrastructure generation, validation, and deployment — so engineers focus on business logic rather than operational plumbing.

### Vision Statement
A unified platform where a business requirement document or plain-language prompt produces a complete, deployed Azure project — architecture diagram, modular microservices, Bicep infrastructure, production readiness review, and live endpoints — orchestrated by intelligent agents with zero manual handoffs.

---

## 3. Product Goals

1. **Automate the full architecture lifecycle** — Convert requirements into deployed Azure projects through 6 orchestrated phases with zero manual handoffs
2. **Generate architecture diagrams from requirements** — AI-driven diagram creation via MCP Draw.io server, producing reusable `.drawio` artifacts
3. **Scaffold production-ready code from diagrams** — Turn architecture diagrams into modular Python microservices with proper service boundaries
4. **Generate and self-heal infrastructure** — Produce Bicep IaC modules with automated validation and auto-fix of syntax, logic, and config errors
5. **Ensure production readiness** — Identify runtime, identity, networking, secret, and monitoring prerequisites before deployment
6. **Enable one-command deployment** — Validate, provision, deploy, and capture endpoints in a single agent invocation
7. **Maintain isolated project outputs** — Each project gets its own folder with docs, diagrams, code, infra, tests, logs, and machine-readable manifest
8. **Provide a reference data pipeline implementation** — Working Fabric Medallion pipeline with multi-source connectors, governance, and observability

---

## 4. User Personas

### 4.1 Cloud Architect / Platform Engineer (Primary)
- **Role:** Designs Azure architectures and establishes infrastructure patterns
- **Pain Points:** Manual diagramming is slow; code scaffolding from diagrams is tedious; IaC errors are discovered too late
- **Goals:** Generate architecture diagrams from requirements, auto-scaffold projects, validate IaC before deployment
- **Needs:** Agent orchestration, diagram generation, Bicep validation, standardized project structure
- **Success Metric:** Time from requirements to deployed project (target: hours, not weeks)

### 4.2 Data Engineer (Primary)
- **Role:** Designs and implements data pipelines
- **Pain Points:** Tired of writing boilerplate retry logic, governance code, and monitoring infrastructure
- **Goals:** Build reliable pipelines quickly with audit trails and clear error reporting
- **Needs:** Well-structured modules, clear configuration options, easy local testing
- **Success Metric:** Time to production deployment (target: 1 day from skeleton to running pipeline)

### 4.3 DevOps Engineer (Secondary)
- **Role:** Deploys and monitors Azure infrastructure; manages CI/CD
- **Pain Points:** Bicep errors discovered at deployment time; inconsistent project structures across teams
- **Goals:** Self-healing IaC, standardized deployment patterns, one-command deployment
- **Needs:** Validated Bicep, production readiness checklists, deployment logs with endpoints
- **Success Metric:** Zero deployment failures from IaC errors

### 4.4 Data Architect (Secondary)
- **Role:** Designs data lake structure and medallion schemas
- **Pain Points:** Needs consistency across teams; lacks enforced governance patterns
- **Goals:** Define reusable templates that teams follow
- **Needs:** Extensible architecture, governance hooks, lineage visibility
- **Success Metric:** Adoption rate and consistency of data quality standards

### 4.5 Data Analyst (Tertiary)
- **Role:** Consumes semantic models in Power BI; occasionally debugs pipeline issues
- **Pain Points:** Doesn't understand why data is missing or late; can't trace root cause
- **Goals:** Clear visibility into data lineage and transformation logic
- **Needs:** Structured logging output, easy-to-read event files, lineage reports
- **Success Metric:** Time-to-issue-resolution and confidence in data freshness

---

## 5. Core Features

### 5.0 AI-Driven Architecture Factory

#### Agent Orchestration System
The factory is powered by 8 custom Copilot agents that automate the full project lifecycle:

| Agent | Role | Phase |
|-------|------|-------|
| **project-orchestrator** | Master controller — drives all phases in sequence | All |
| **project-state-manager** | Maintains project folders, logs, and `project-manifest.json` | 0 |
| **brd-to-architecture-diagram** | Parses requirements and generates Azure Draw.io diagrams via MCP | 1 |
| **drawio-architecture-reader** | Analyzes `.drawio` files and extracts component inventory | 1-2 |
| **azure-architecture-implementer** | Reads diagrams, scaffolds Python services + Bicep IaC | 2 |
| **bicep-infrastructure-validator** | Auto-detects and auto-fixes Bicep syntax/logic/config errors | 3 |
| **production-environment-advisor** | Identifies runtime, Azure, identity, and deployment prerequisites | 4 |
| **azure-project-deployer** | Validates and deploys Bicep to Azure, captures outputs | 5 |

#### Architecture Diagram Generation
- Converts BRD/PRD/plain-language prompts into Azure architecture diagrams
- Uses MCP Draw.io server for programmatic diagram creation (transactional workflow)
- Produces `.drawio` files with companion `.md` notes documenting components and data flows
- Follows Azure Well-Architected Framework layout conventions

#### Automatic Code Scaffolding
- Reads architecture diagrams and maps components to Azure resources
- Generates modular Python microservices with proper service boundaries
- Produces shared libraries for common patterns (config, resilience, models)
- Creates per-service README files and configuration guides

#### Self-Healing Bicep Infrastructure
- Generates modular Bicep templates (one per resource type)
- Auto-detects common errors: `substr()` → `substring()`, invalid properties, type mismatches, missing `@secure()`, broken module paths
- Auto-fixes all detected errors and re-validates to confirm resolution
- Produces structured validation reports

#### Project Isolation and State Management
- Each project lives in `projects/<name>/` with standardized structure
- Machine-readable `project-manifest.json` tracks phase statuses, artifacts, timestamps
- Per-phase logs with ISO timestamps for full auditability
- `orchestration.log` provides end-to-end execution trace

#### Architecture Diagram Gallery
Pre-built reference architectures in `diagrams/`:
- Azure AI Foundry (agentic applications)
- Azure AI Foundry WAF (Well-Architected Framework)
- Azure API Management + Container Apps + Cosmos DB
- Azure Event Grid + Functions + Computer Vision
- Microsoft Fabric Lakehouse (medallion pattern)
- Fabric Medallion Architecture

### 5.1 Medallion Layer Architecture (Reference Implementation)
Three-tier data transformation model:

#### **Bronze Layer** (Raw Ingestion)
- Ingests data from multiple sources as-is (ADLS Gen2, Snowflake)
- Records source lineage and ingestion metadata
- Validates presence of required fields
- Output: Raw records with source attribution

#### **Silver Layer** (Cleansing & Deduplication)
- Normalizes field values (whitespace trimming, case standardization, date parsing)
- Deduplicates on (customer_id, event_time, event_type) composite key
- Calculates data quality score per record
- Output: Cleansed, deduplicated records

#### **Gold Layer** (Semantic Aggregation)
- Builds customer-level metrics (total_amount, event_count)
- Builds event-type aggregations
- Creates ready-for-analysis semantic models
- Output: Analyst-ready fact tables for Power BI

**Design Principle:** Strict layer separation; each layer depends only on the previous one.

### 5.2 Multi-Source Data Connectors

#### **ADLS Gen2 Connector**
- Reads JSONL files from Azure Data Lake Storage
- Supports connection string and managed identity (DefaultAzureCredential) auth
- Configurable operation timeout and retry behavior
- Error handling: transient failures auto-retry; auth failures fail fast

#### **Snowflake Connector**
- Executes configurable SQL queries (e.g., `SELECT * FROM events ASC LIMIT 100`)
- Supports login and network timeout configuration
- Handles transient connection failures with exponential backoff
- Secure credential management via environment variables

#### **Extensible Architecture**
- `Connector` base interface allows adding sources (BigQuery, Redshift, Databricks, etc.)
- Sample data mode allows local testing without cloud credentials

### 5.3 Cloud Analytics Integration

#### **Power BI Publisher**
- Exports semantic models to local JSON file (`outputs/powerbi/semantic_model.json`)
- Pushes customer_metrics and event_type_metrics to Power BI REST API
- Acquires access tokens via service principal (direct token or MSAL OAuth)
- Integrated retry logic with exponential backoff for transient failures

### 5.4 Structured Observability

#### **Structured Logging**
- All pipeline events emitted to `outputs/logs/events.jsonl` (append-only)
- JSON format: `{"timestamp": "...", "stage": "bronze|silver|gold|...", "action": "...", "level": "info|warn|error", "payload": {...}}`
- Event summary: total count, breakdown by level and stage
- Use case: Splunk, Data Explorer, ELK ingestion; compliance audits; debugging

#### **Alert Management System**
- **ConsoleAlertHandler** — Prints alerts to stdout (default for dev/test)
- **WebhookAlertHandler** — POSTs alert JSON to webhook URL (Slack, Teams, custom systems)
- **EmailAlertHandler** — Stub for email integration (extensible)
- Severity-based filtering (info/warn/error/critical)
- Example: Critical errors trigger webhook → Slack notification → on-call alert

### 5.5 Enterprise Governance

#### **Lineage Tracking**
- `DataGovernance` class records layer→schema→record_count per transformation
- Timestamped lineage entries for audit trail
- Output: Complete data flow history for compliance and debugging

#### **Field-Level Security**
- `SecurityContext` class masks sensitive fields (e.g., customer_id → `***1001`)
- Token-based authorization for pipeline execution
- Configurable masking rules per field

#### **Data Validation**
- Required field validation at Bronze layer
- Schema enforcement via dataclasses (RawRecord, SilverRecord)
- Quality scoring per record (1.0 = clean, < 1.0 = data issues)

### 5.6 Production Resilience

#### **Automatic Retry Logic**
- `run_with_retry()` helper with exponential backoff
- Configurable attempt count (default: 3) and base delay (default: 1.5 seconds)
- Delay formula: `delay = base_delay * (2 ^ attempt)`
- Per-connector timeouts: ADLS (30s), Snowflake (15s login, 30s network), Power BI (30s)

#### **Error Handling**
- Transient failures (network timeout, HTTP 429): auto-retry
- Auth failures (invalid credentials): fail fast, emit CRITICAL alert
- Graceful degradation: sample mode works without cloud credentials
- Pipeline exception → structured log error + webhook alert

#### **Configuration Management**
- **Environment-driven:** All settings via `.env` file
- **CLI overrides:** `--mode auto|sample|real` flag overrides environment setting
- **Defaults:** Sensible defaults for all retry/timeout parameters
- **Schema:** `PipelineConfig` dataclass enforces configuration structure

### 5.7 Local-to-Cloud Developer Experience

#### **Sample Mode (Offline Development)**
```bash
python .\fabric_medallion\run_pipeline.py --mode sample
```
- Uses local JSON files for Bronze and Snowflake data
- No cloud credentials required
- Identical data flow to production
- Output: Same structured logs and semantic models

#### **Real Mode (Azure Integration)**
```bash
python .\fabric_medallion\run_pipeline.py --mode real
```
- Loads data from ADLS Gen2 and Snowflake (live)
- Publishes to Power BI (if configured)
- Full retry/timeout behavior active
- Structured logs capture all cloud interactions

#### **Auto Mode (Default)**
```bash
python .\fabric_medallion\run_pipeline.py
```
- Checks environment configuration; uses real if configured, else sample
- Allows gradual adoption: develop locally, deploy to cloud with one env change

---

## 6. Technical Architecture

### 6.1 Factory Orchestration Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                  AZURE ARCHITECTURE FACTORY                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  INPUT                 AGENT ORCHESTRATION PIPELINE                   │
│                                                                        │
│  ┌──────────────┐      ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ BRD / PRD /  │─────→│ Phase 0  │──→│ Phase 1  │──→│ Phase 2  │  │
│  │ Prompt       │      │ Setup    │   │ Diagram  │   │ Scaffold │  │
│  └──────────────┘      └──────────┘   └──────────┘   └──────────┘  │
│                              │              │              │          │
│                              ▼              ▼              ▼          │
│                         project/       .drawio +      src/ +         │
│                         manifest       notes.md       infra/         │
│                                                                        │
│                        ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│                        │ Phase 3  │──→│ Phase 4  │──→│ Phase 5  │  │
│                        │ Validate │   │ Review   │   │ Deploy   │  │
│                        └──────────┘   └──────────┘   └──────────┘  │
│                              │              │              │          │
│                              ▼              ▼              ▼          │
│                         Fixed Bicep   Prerequisites   Endpoints      │
│                         + Report      + Checklist     + Outputs      │
│                                                                        │
│  OUTPUTS                                                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ projects/<name>/                                                │  │
│  │ ├── diagrams/         Architecture .drawio + companion notes   │  │
│  │ ├── src/              Scaffolded Python microservices           │  │
│  │ ├── infra/            Validated Bicep modules + params          │  │
│  │ ├── docs/             Requirements, READMEs, deploy guides     │  │
│  │ ├── tests/            Service-level tests                       │  │
│  │ ├── logs/             Per-phase logs + orchestration.log        │  │
│  │ └── project-manifest.json   Phase statuses + artifact index    │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 Reference Implementation: Medallion Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MEDALLION PIPELINE (REFERENCE)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐         ┌──────────┐   ┌──────────┐              │
│  │ ADLS Gen2    │──┐      │  BRONZE  │──→│  SILVER  │──┐          │
│  └──────────────┘  ├─────→│ Validate │   │ Cleanse  │  │          │
│  ┌──────────────┐  │      └──────────┘   └──────────┘  │          │
│  │ Snowflake    │──┘                                     ▼          │
│  └──────────────┘                                  ┌──────────┐    │
│                                                     │   GOLD   │    │
│  Power BI ←─── Semantic Models ←─── Aggregations ──│Aggregate │    │
│  Logs     ←─── Structured Events ←── Governance    └──────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Agent Framework** | VS Code Copilot Agents (`.agent.md`) | 8 custom agents driving the factory lifecycle |
| **Diagram Server** | MCP Draw.io | Programmatic architecture diagram generation |
| **Infrastructure** | Bicep (modular) | Azure IaC with per-resource-type modules |
| **Language** | Python 3.9+ | Cross-platform, data-science native |
| **Data Models** | dataclasses | Type-safe, lightweight schemas |
| **ADLS Connector** | azure-storage-file-datalake | Direct access to Azure Data Lake |
| **Auth** | azure-identity | Managed identity support for passwordless auth |
| **Snowflake** | snowflake-connector-python | Native Snowflake SQL execution |
| **Power BI** | msal, requests | OAuth token acquisition and REST API |
| **Testing** | unittest | No external test framework dependency |
| **Config** | python-dotenv | Environment variable management (optional) |
| **Logging** | json (stdlib) | Structured JSON event output |
| **Orchestration** | Custom scheduler | Simple loop-based pipeline runner |

### 6.4 Repository Structure

```
azure-architecture-factory/
├── .github/
│   ├── agents/                  # 8 custom Copilot agent definitions
│   └── copilot-instructions.md  # Repo-level Copilot configuration
├── diagrams/                    # Architecture diagram gallery (.drawio + .md)
├── infra/                       # Bicep IaC modules (ai, compute, data, monitoring, security)
│   ├── main.bicep
│   ├── modules/
│   └── params/                  # dev / test / prod parameter files
├── fabric_medallion/            # Reference implementation: Fabric Medallion pipeline
│   ├── bronze_fabric/           # Bronze layer (ingest + validate)
│   ├── silver_fabric/           # Silver layer (cleanse + dedupe)
│   ├── gold_fabric/             # Gold layer (aggregate)
│   ├── connectors/              # ADLS Gen2, Snowflake connectors
│   ├── common/                  # Config, models, resilience, governance, logging
│   ├── power_bi_engine/         # Semantic model publisher
│   ├── tests/                   # Unit tests (6 passing)
│   └── run_pipeline.py          # Pipeline entrypoint with --mode CLI
├── projects/                    # Isolated project outputs (one folder per project)
│   └── <project-name>/
│       ├── project-manifest.json
│       ├── diagrams/ src/ infra/ tests/ logs/ docs/
├── BRD.md / PRD.md / QUICKSTART.md / USE_CASES_AND_PROBLEMS_SOLVED.md
└── README.md
```

---

## 7. Feature Specifications

### 7.1 Data Model Schemas

#### RawRecord (Bronze Output)
```python
@dataclass
class RawRecord:
    customer_id: str
    event_time: str
    event_type: str
    amount: float
    source: str                    # "adls-gen2" or "snowflake-mirror"
    metadata: dict
```

#### SilverRecord (Silver Output)
```python
@dataclass
class SilverRecord:
    customer_id: str
    event_date: str               # Extracted from event_time
    event_type: str               # Normalized (lowercase)
    amount: float                 # Validated, non-negative
    source: str
    quality_score: float          # 1.0 = clean, < 1.0 = issues
```

#### Gold Output
```python
{
    "customer_metrics": [
        {"customer_id": "C1001", "total_amount": 165.5, "event_count": 2},
        ...
    ],
    "event_type_metrics": [
        {"event_type": "purchase", "total_amount": 1250.0},
        ...
    ]
}
```

### 7.2 Configuration Schema (PipelineConfig)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_real_connectors` | bool | False | Use cloud connectors or sample data |
| `connector_retries` | int | 3 | Retry attempts for transient failures |
| `retry_backoff_seconds` | float | 1.5 | Base delay between retries |
| `adls_operation_timeout_seconds` | int | 30 | ADLS operation timeout |
| `snowflake_login_timeout_seconds` | int | 15 | Snowflake login timeout |
| `snowflake_network_timeout_seconds` | int | 30 | Snowflake network timeout |
| `powerbi_timeout_seconds` | int | 30 | Power BI API timeout |
| `adls_connection_string` | str | "" | ADLS Gen2 connection string (optional) |
| `snowflake_account` | str | "" | Snowflake account identifier |
| `snowflake_query` | str | "" | SQL query to execute |
| `powerbi_workspace_id` | str | "" | Power BI workspace GUID |
| `powerbi_dataset_id` | str | "" | Power BI dataset GUID |

### 7.3 Logging Schema

All events written to `events.jsonl`:

```json
{
  "timestamp": "2026-03-18T16:27:56.807271+00:00",
  "stage": "bronze|silver|gold|pipeline|powerbi|security",
  "action": "ingest|transform|build|publish|error|...",
  "level": "info|warn|error|critical",
  "payload": {
    "custom": "fields",
    "counts": 123,
    "error_type": "...",
    "error_message": "..."
  }
}
```

**Queryable Fields:**
- `timestamp` — machine-readable ISO 8601 with UTC timezone
- `stage` — which medallion layer or subsystem
- `action` — what operation occurred
- `level` — severity for filtering
- `payload` — contextual details (row counts, error info, etc.)

---

## 8. Success Metrics

### 8.1 Factory Automation
- **Requirements-to-deployment time:** < 4 hours (target: zero manual handoffs)
- **Diagram generation success rate:** > 95% (valid `.drawio` on first attempt)
- **Bicep auto-fix rate:** > 90% (errors detected and resolved without human intervention)
- **Deployment success rate:** > 95% (one-command deploy with no manual config)
- **Project isolation compliance:** 100% (every project has manifest + standardized folder structure)

### 8.2 Development Productivity
- **Time to scaffold:** < 5 minutes
- **Time to first production run:** < 1 day (from skeleton to live pipeline)
- **Code reuse across projects:** > 80% (common modules leveraged)

### 8.2 Operational Reliability
- **Pipeline success rate:** > 99% (with auto-retry)
- **Mean time to recovery (MTTR):** < 5 minutes (via structured logs)
- **Data freshness:** Daily or on-demand (configurable)
- **Alert response time:** < 1 minute (webhook alerts)

### 8.3 Data Quality
- **Data validation pass rate:** > 95% (required fields present)
- **Deduplication effectiveness:** > 90% (removes near-duplicates)
- **Quality score distribution:** 90% records score 1.0 (clean)

### 8.4 Observability
- **Event logging completeness:** 100% (all operations logged)
- **Lineage traceability:** 100% (full source-to-gold path)
- **Alert delivery latency:** < 30 seconds (webhook)

---

## 9. Out-of-Scope (V2+ Roadmap)

### Factory Roadmap
- **Additional project templates** (e.g., Event-Driven, CQRS, Microservice API gateway)
- **Terraform and Pulumi IaC backends** (alongside Bicep)
- **CI/CD pipeline generation** (GitHub Actions / Azure DevOps from project manifest)
- **Multi-cloud support** (AWS CloudFormation, GCP Deployment Manager)
- **Custom agent plugins** (user-defined agents for domain-specific patterns)
- **Diagram diff and versioning** (track architecture evolution across commits)

### Pipeline Roadmap
- **Data retention policies** (auto-archive old bronze records)
- **Incremental/CDC modes** (only process new/changed records)
- **ML-driven quality scoring** (anomaly detection on quality metrics)
- **Schema evolution** (auto-detect schema changes; data type migrations)
- **Partition pruning** (date-based, location-based partitioning)
- **Streaming ingestion** (Apache Kafka, Event Hubs)
- **Data masking policies** (configurable per field/role)
- **Cost optimization** (storage tier analytics; compute right-sizing)
- **Multi-tenant support** (isolated namespaces per tenant)

---

## 10. Constraints & Assumptions

### Constraints
- **Data volume:** Current design supports < 10GB per daily run (scaling via partitioning in V2)
- **Latency:** Designed for batch/hourly cadence, not real-time streaming
- **Cost:** Assumes pay-as-you-go Azure (ADLS Gen2, Power BI Premium recommended)
- **Availability:** Single-region deployment (multi-region in V2)

### Assumptions
- **Networks:** Reliable internet connectivity for cloud API calls
- **Credentials:** Secrets stored securely in `.env` or Azure Key Vault
- **Data format:** Input is structured JSON/CSV (semi-structured data requires preprocessing)
- **Schema stability:** Bronze schema matches Silver/Gold expectations
- **Compliance:** Organisation provides compliance framework; pipeline logs to external audit system

---

## 11. Testing & Validation

### Unit Tests (Passing ✅)
- **Bronze ingest:** Validates required fields, records lineage
- **Silver dedupe:** Removes duplicates, normalizes values, calculates quality
- **Gold aggregation:** Builds customer and event_type metrics
- **CLI modes:** Overrides environment settings correctly

### Integration Tests (Manual)
- End-to-end sample mode run (no cloud creds required)
- Real mode with ADLS + Snowflake (requires Azure subscription)
- Webhook alert delivery (with ngrok for local testing)
- Structured logging to file system

### Load Testing (Future)
- Bulk ingest (100K+ records per day)
- Large aggregate tables (10K+ unique customers)
- Multi-hour pipeline runs (garbage collection, memory stability)

---

## 12. Rollout Plan

### Phase 1: Internal (Weeks 1-2)
- Finalize documentation
- Conduct internal testing across sample scenarios
- Gather feedback from data engineers

### Phase 2: Pilot (Weeks 3-4)
- Deploy to 1-2 pilot projects (real cloud connectors)
- Monitor stability and operational readiness
- Refine documentation based on real-world usage

### Phase 3: GA (Week 5+)
- Release to production
- Publish on internal repository / template library
- Provide training and onboarding for data teams

---

## 13. Glossary

| Term | Definition |
|------|-----------|
| **Architecture Factory** | AI-driven platform that converts requirements into deployed Azure projects via agent orchestration |
| **Copilot Agent** | A custom VS Code agent (`.agent.md`) that performs a specific phase of the factory lifecycle |
| **MCP Draw.io** | Model Context Protocol server for programmatic Draw.io diagram generation |
| **Project Manifest** | Machine-readable `project-manifest.json` tracking phase statuses and artifact paths |
| **Self-Healing IaC** | Automated detection and correction of Bicep syntax/logic/config errors by the validator agent |
| **Medallion Architecture** | Three-tier data lake design: Bronze (raw), Silver (cleaned), Gold (analytics-ready) |
| **Transactional Semantics** | Each record has clear source attribution, transformation history, and quality score |
| **Lineage** | Complete audit trail of data flow from source through all transformations |
| **Deduplication** | Removal of exact duplicates based on (customer_id, event_time, event_type) key |
| **Quality Score** | Metric indicating data cleanliness (1.0 = perfect, < 1.0 = issues detected) |
| **Managed Identity** | Azure AD identity for passwordless authentication (DefaultAzureCredential) |
| **Exponential Backoff** | Retry strategy with increasing delays: 1.5s, 3s, 6s, ... prevents server overload |
| **Semantic Model** | Business-ready data structure optimized for analytics queries |

---

## 14. Sign-Off

**Product Owner:** Cloud Architecture & Data Engineering Leadership  
**Technical Lead:** Platform Engineering  
**Release Date:** March 19, 2026  
**Status:** ✅ Production Ready
