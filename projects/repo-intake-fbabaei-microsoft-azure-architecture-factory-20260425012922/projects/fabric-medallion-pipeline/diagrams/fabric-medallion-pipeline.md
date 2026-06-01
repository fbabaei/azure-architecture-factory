# Fabric Medallion Architecture Pipeline

## Overview

The Fabric Medallion Architecture Pipeline provides a production-grade, open architecture data platform built on Azure. It transforms raw data from multiple sources (ADLS Gen2, Snowflake Mirror) through three medallion layers—Bronze (raw), Silver (validated), Gold (aggregated)—and serves business-ready data to Power BI and semantic models. The platform embeds resilience (auto-retry, circuit breaker), governance (lineage, field masking, audit logging), and observability (Application Insights, Log Analytics, Azure Monitor) as first-class concerns—not afterthoughts.

---

## Components

| Component | Azure Service | Role | Group |
|-----------|--------------|------|-------|
| ADLS Gen2 (Raw Events) | Azure Data Lake Storage Gen2 | Primary raw event source for ingestion | Data Sources |
| Snowflake Mirror | Snowflake / Microsoft Fabric Mirroring | Secondary source: mirrored analytical data | Data Sources |
| Data Ingestion Service | Azure Container Apps (Python) | Orchestrates ingestion, applies resilience policies (retry, timeout) | Medallion Pipeline |
| Bronze Layer | ADLS Gen2 (bronze/ partition) | Stores raw, unvalidated data; append-only | Medallion Pipeline |
| Silver Layer | ADLS Gen2 (silver/ partition) | Cleansed, validated, deduplicated data | Medallion Pipeline |
| Gold Layer | ADLS Gen2 (gold/ partition) | Business-aggregated data; customer metrics, event metrics | Medallion Pipeline |
| Governance & Lineage Engine | Python shared library (governance.py) | Field masking, audit event emission, data lineage tracking | Medallion Pipeline |
| Resilience & Error Handling | Python shared library (resilience.py) | Auto-retry with exponential backoff, timeout protection, circuit breaker | Medallion Pipeline |
| Power BI Reports | Microsoft Power BI | Interactive dashboards for analytics consumers | Analytics & Reporting |
| Semantic Model | Power BI Semantic Model / Fabric | Self-service analytics layer over Gold data | Analytics & Reporting |
| Azure Key Vault | Azure Key Vault | Secrets and credential management (connection strings, API keys) | Cross-Cutting |
| Managed Identity | Azure Managed Identity | Passwordless authentication for all Azure service-to-service calls | Cross-Cutting |
| Application Insights | Azure Application Insights | Telemetry, APM, distributed tracing across pipeline stages | Cross-Cutting |
| Log Analytics Workspace | Azure Log Analytics | Structured log event aggregation; KQL queries for incident investigation | Cross-Cutting |
| Azure Monitor | Azure Monitor + Alerts | Proactive alerting on pipeline failures, SLA breaches, cost thresholds | Cross-Cutting |
| Microsoft Entra ID | Microsoft Entra ID | RBAC enforcement; token-based authorization for all API access | Cross-Cutting |
| Azure Container Registry | Azure Container Registry | Docker image storage for Container Apps; immutable image tags per release | Cross-Cutting |

---

## Primary Data Flow

```
[ADLS Gen2]       ─┐
                    ├──► [Data Ingestion Service] ──► [Bronze Layer] ──► [Silver Layer] ──► [Gold Layer] ──► [Power BI]
[Snowflake Mirror] ─┘                                                                                    └──► [Semantic Model]
```

### Stage-by-Stage Detail

| Stage | Input | Transform | Output | Schema |
|-------|-------|-----------|--------|--------|
| **Ingest** | ADLS events (JSONL), Snowflake mirror (JSONL) | Resilience wrapper, audit event | Bronze JSONL | Raw event schema |
| **Bronze → Silver** | Raw JSONL | Validation, deduplication, field masking | Silver JSONL | Cleaned event schema |
| **Silver → Gold** | Cleaned JSONL | Aggregation by customer, event type, time window | Gold JSONL | Customer metrics, event metrics |
| **Gold → Analytics** | Gold JSONL | Power BI semantic model publication | PBI dataset | Star schema |

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Compute | Azure Container Apps | Serverless-friendly, Python-native, cost-efficient; no K8s overhead |
| Storage | ADLS Gen2 (partitioned by layer) | Azure-native, hierarchical namespace, Fabric-compatible |
| Pipeline pattern | Medallion (Bronze/Silver/Gold) | Industry standard; enables incremental quality improvement |
| Resilience | exponential backoff + circuit breaker | Eliminates silent failures; fulfills 99.5% success rate KR |
| Governance | Built-in (not add-on) | Mandatory lineage + masking from day 1; GDPR/SOC2 compliance |
| Authentication | Managed Identity (passwordless) | Eliminates credential leakage; Azure best practice |
| Observability | Application Insights + Log Analytics | Full distributed tracing + structured event querying via KQL |
| IaC | Bicep (modular) | Azure-native, readable, supports parameter files per environment |
| CI/CD artifacts | Azure Container Registry | Immutable image versioning; integrates with Container Apps revisions |

---

## Non-Functional Requirements Met

| Requirement | Implementation |
|-------------|---------------|
| **Reliability (99.5% pipeline success)** | Auto-retry with exponential backoff; circuit breaker; configurable timeout |
| **Data freshness (< 24h)** | Scheduled Container Apps jobs; incremental ingestion support |
| **MTTR < 15 min** | Structured logs + Application Insights distributed traces narrow root cause fast |
| **Compliance (GDPR/SOC2/HIPAA)** | Field masking on ingest; full lineage audit trail; no raw PII in Silver/Gold |
| **Cloud cost efficiency** | Retry limits prevent runaway API calls; Container Apps scale-to-zero |
| **Self-service analytics** | Gold layer + Power BI semantic model eliminates analyst–engineer bottleneck |

---

## Azure Resource Mapping

| Azure Resource | SKU / Tier | Purpose |
|----------------|-----------|---------|
| ADLS Gen2 | Standard LRS | Bronze/Silver/Gold storage partitions |
| Azure Container Apps | Consumption plan | Pipeline execution (bronze, silver, gold services) |
| Azure Key Vault | Standard | Secrets: ADLS connection string, Snowflake credentials, Power BI token |
| Application Insights | Pay-as-you-go | Telemetry, distributed tracing |
| Log Analytics Workspace | Pay-as-you-go | Structured log sink for all pipeline events |
| Azure Monitor | Standard | Alerts: pipeline failure rate, latency, cost threshold |
| Microsoft Entra ID | Tenant-included | RBAC; Managed Identity assignment |
| Azure Container Registry | Basic | Docker images for pipeline services |

---

## Diagram Source

- **Mode**: Mode A — Generated via MCP Draw.io workflow (brd-to-architecture-diagram)
- **Source requirements**: `projects/fabric-medallion-pipeline/docs/requirements.md`
- **Diagram file**: `projects/fabric-medallion-pipeline/diagrams/fabric-medallion-pipeline.drawio`
- **Generated**: 2026-03-19
