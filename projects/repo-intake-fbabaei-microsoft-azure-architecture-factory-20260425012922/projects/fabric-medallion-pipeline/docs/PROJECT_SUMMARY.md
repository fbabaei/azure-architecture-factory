# Fabric Medallion Architecture Pipeline — One-Page Summary

**Version:** 1.0 | **Date:** March 30, 2026 | **Environment:** Dev / East US

---

## What It Is

A **production-grade, open-architecture data pipeline** built on Azure that transforms raw multi-source data through three quality layers (Bronze → Silver → Gold) and delivers business-ready analytics to Power BI. Governance, resilience, and observability are first-class concerns built into every layer — not retrofitted.

---

## Business Problem Solved

| Pain Point | Impact Before |
|---|---|
| Engineers spend 60–70% of effort on plumbing (retry, logging, governance) | 4–6 week time-to-value per analytics project |
| Pipelines fail silently; root cause takes hours | Stale data, lost trust, on-call burnout |
| No audit trail; sensitive data exposed in logs | GDPR/SOC2/HIPAA compliance risk |
| ADLS → Power BI sync requires manual steps | 24+ hour data latency for analysts |

---

## Architecture — Medallion Layers

```
┌─────────────────────┐     ┌──────────────────────────────────────────────────────────┐     ┌──────────────────┐
│    DATA SOURCES      │     │                MEDALLION PIPELINE                        │     │    ANALYTICS     │
│                      │     │                                                          │     │                  │
│  ADLS Gen2           ├────►│  Ingestion ──► BRONZE ──► SILVER ──► GOLD              ├────►│  Power BI        │
│  (Raw Events)        │     │  (Container    (Raw,      (Cleansed, (Aggregated,        │     │  Reports         │
│                      │     │   Apps)        append-    validated, customer &          │     │                  │
│  Snowflake Mirror    ├────►│               only)      masked)    event metrics)      ├────►│  Semantic Model  │
└─────────────────────┘     └──────────────────────────────────────────────────────────┘     └──────────────────┘
```

| Layer | Storage | Transform Applied |
|---|---|---|
| **Bronze** | ADLS Gen2 `bronze/` | Raw append-only; audit event emitted on ingest |
| **Silver** | ADLS Gen2 `silver/` | Validation, deduplication, PII field masking |
| **Gold** | ADLS Gen2 `gold/` | Aggregation by customer, event type, time window → star schema |

---

## Key Azure Resources

| Resource | SKU | Role |
|---|---|---|
| Azure Container Apps | Consumption | Runs Bronze / Silver / Gold / Orchestrator services |
| ADLS Gen2 | Standard LRS | Partitioned storage for all three medallion layers |
| Azure Key Vault | Standard | Secrets: ADLS conn string, Snowflake creds, PBI token |
| Application Insights | Pay-as-you-go | Distributed tracing and APM across all pipeline stages |
| Log Analytics Workspace | Pay-as-you-go | Structured event aggregation; KQL incident investigation |
| Azure Monitor | Standard | Proactive alerts: failure rate, latency, cost thresholds |
| Azure Container Registry | Basic | Immutable Docker images per pipeline service release |
| Microsoft Entra ID + Managed Identity | Tenant-included | Passwordless auth; RBAC enforcement across all services |

---

## Cross-Cutting Capabilities

| Capability | Implementation |
|---|---|
| **Resilience** | `shared_lib/resilience.py` — exponential backoff, configurable timeout, circuit breaker |
| **Governance** | `shared_lib/governance.py` — field masking, lineage tracking, audit event emission |
| **Observability** | Application Insights traces + Log Analytics structured logs + Azure Monitor alerts |
| **Security** | Managed Identity (passwordless), Key Vault secrets, Entra ID RBAC |
| **IaC** | Bicep modules under `infra/` — parameterised per environment (`dev.bicepparam`) |

---

## Non-Functional Requirements

| Requirement | Target | Mechanism |
|---|---|---|
| Pipeline success rate | ≥ 99.5% | Auto-retry + circuit breaker |
| Data freshness | < 24 hours | Scheduled Container Apps jobs; incremental ingest |
| MTTR | < 15 minutes | Distributed traces narrow root cause instantly |
| Compliance | GDPR / SOC2 / HIPAA | PII masked at Silver; full lineage audit trail |
| Cost | Scale-to-zero | Container Apps Consumption plan; retry limits |

---

## Microservice Breakdown

| Service | Path | Responsibility |
|---|---|---|
| `bronze-ingestion` | `src/bronze-ingestion/` | Pulls from ADLS Gen2 + Snowflake Mirror; writes raw JSONL to Bronze |
| `silver-processor` | `src/silver-processor/` | Reads Bronze; validates, deduplicates, masks PII; writes to Silver |
| `gold-aggregator` | `src/gold-aggregator/` | Reads Silver; aggregates metrics; writes star-schema Gold |
| `pipeline-orchestrator` | `src/pipeline-orchestrator/` | Schedules and coordinates stage execution; emits pipeline-level telemetry |
| `shared_lib` | `src/shared_lib/` | Resilience, governance, config, telemetry — shared across all services |

---

## Project Status

| Phase | Status |
|---|---|
| Architecture design (Draw.io diagram + notes) | ✅ Complete |
| Implementation (all services + shared lib) | ✅ Complete |
| Infrastructure validation (Bicep) | ✅ Complete — 0 errors |
| Production readiness review | ⏳ Not started |
| Azure deployment | Not requested |
