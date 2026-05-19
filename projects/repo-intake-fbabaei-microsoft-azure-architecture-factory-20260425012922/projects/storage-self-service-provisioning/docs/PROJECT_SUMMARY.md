# Storage Self-Service Provisioning Platform — One-Page Summary

**Version:** 1.0 | **Date:** March 30, 2026 | **Status:** Implementation Complete

---

## What It Is

A **governed, automated web platform** that allows authorized users to request, approve, and receive Azure storage resources (Storage Accounts, ADLS Gen2 containers) in minutes — replacing a 3–10 day manual IT process. Every provisioned resource is policy-checked, tagged, classified, and registered in Microsoft Purview before it is handed to the requester.

---

## Business Problem Solved

| Pain Point | Impact Before |
|---|---|
| Manual provisioning: tickets, CLI scripts, no automation | 3–10 day lead time per request; 200+ requests/year blocked |
| No governance at provisioning time — tagging and Purview registration ad-hoc | Failed audits; cost attribution errors; lineage gaps |
| Secrets in scripts and tickets; over-privileged accounts | Credential leakage risk; compliance violations |
| No status visibility — requester has to chase via email | Repeated follow-up; no SLA enforcement |

---

## Architecture Overview

```
┌──────────────────┐     ┌─────────────────────────────────────────────────────────────┐     ┌─────────────────────┐
│   REQUESTER      │     │                  PLATFORM                                   │     │   AZURE RESOURCES   │
│                  │     │                                                              │     │                     │
│  Web Portal /    ├────►│  Provisioning API ──► Workflow Worker                      ├────►│  Storage Account    │
│  REST Client     │     │  (FastAPI)             │                                    │     │  ADLS Gen2          │
│                  │     │                        ├──► Validation & Policy Check       │     │  (Tagged, Purview-  │
│  Entra ID Auth   │     │                        ├──► Storage Provisioning            │     │   registered,       │
└──────────────────┘     │                        ├──► Governance & Purview            │     │   least-privilege)  │
                         │                        └──► Event Emission                  │     └─────────────────────┘
                         │                                                              │
                         │  ┌────────────┐  ┌──────────┐  ┌────────────┐              │
                         │  │ Cosmos DB  │  │Event Grid│  │ Key Vault  │              │
                         │  │ (state)    │  │(events)  │  │ (secrets)  │              │
                         └──┴────────────┴──┴──────────┴──┴────────────┴──────────────┘
```

---

## Provisioning Workflow — Stage by Stage

| Stage | Action | Outcome |
|---|---|---|
| **Request Intake** | Requester submits project, team, environment, data class | Request stored in Cosmos DB; `PENDING` state |
| **Validation** | Policy check: naming convention, quota, data class allowed | Blocked if policy fails; requester notified |
| **Provisioning** | Azure Storage Account or ADLS Gen2 container created | Resource live; tagged with team, env, classification |
| **Governance** | Purview registration + data classification applied | Asset catalogued with full lineage |
| **Event Emission** | Lifecycle events published to Event Grid | Downstream consumers notified; audit trail complete |
| **Status** | Requester queries API for real-time status | `PENDING → VALIDATING → PROVISIONING → COMPLETE` |

---

## Key Azure Resources

| Resource | Role |
|---|---|
| Azure Container Apps | Hosts Provisioning API (FastAPI) and Workflow Worker |
| Azure Cosmos DB | Stores request state and audit events |
| Azure Storage / ADLS Gen2 | Target — the storage being provisioned |
| Azure Event Grid | Publishes provisioning lifecycle events |
| Azure Key Vault | Stores all secrets (Cosmos conn string, Event Grid key, Storage key) |
| Microsoft Purview | Data asset registration and classification |
| Microsoft Entra ID + Managed Identity | Authentication (requesters) and passwordless service-to-service auth |
| Azure Monitor + Application Insights | Metrics, logs, distributed tracing, and alerting |

---

## Microservice Breakdown

| Service | Path | Responsibility |
|---|---|---|
| `provisioning_api` | `src/provisioning_api/main.py` | FastAPI: request intake, status retrieval, Entra ID auth |
| `workflow_worker` | `src/workflow_worker/main.py` | Processes pending requests through validation → provisioning → governance |
| `shared_lib/config` | `src/shared_lib/config.py` | Environment-driven config; Key Vault secret resolution |
| `shared_lib/models` | `src/shared_lib/models.py` | Shared data models (ProvisioningRequest, RequestStatus) |
| `shared_lib/repository` | `src/shared_lib/repository.py` | Pluggable backend: `local` (dev) or `cosmos` (prod) |
| `shared_lib/storage_provider` | `src/shared_lib/storage_provider.py` | Pluggable backend: `local` (dev) or `azure` (prod) |
| `shared_lib/governance` | `src/shared_lib/governance.py` | Purview registration, tagging, classification |
| `shared_lib/resilience` | `src/shared_lib/resilience.py` | Exponential backoff, circuit breaker, timeout |
| `shared_lib/monitoring` | `src/shared_lib/monitoring.py` | Application Insights telemetry, structured logging |
| `shared_lib/secrets` | `src/shared_lib/secrets.py` | Key Vault secret resolution via managed identity |

---

## Cross-Cutting Capabilities

| Capability | Implementation |
|---|---|
| **Authentication** | Microsoft Entra ID for requesters; Managed Identity for all service calls |
| **Secret Management** | Key Vault; env vars resolved at runtime — zero embedded secrets |
| **Resilience** | `shared_lib/resilience.py` — exponential backoff, circuit breaker, configurable timeout |
| **Governance** | `shared_lib/governance.py` — Purview registration, mandatory tagging, data classification |
| **Pluggable Backends** | `local` (dev/test) ↔ `azure` (prod) — switch via env vars, no code changes |
| **Observability** | App Insights distributed tracing + Azure Monitor alerts + structured Cosmos audit log |

---

## Pluggable Backend Configuration

| Backend | Env Var | Values |
|---|---|---|
| Request repository | `REQUEST_REPOSITORY_BACKEND` | `local` / `cosmos` |
| Storage provisioner | `STORAGE_PROVISIONER_BACKEND` | `local` / `azure` |
| Event publisher | `EVENT_PUBLISHER_BACKEND` | `log` / `eventgrid` |

---

## Non-Functional Requirements

| Requirement | Target | Mechanism |
|---|---|---|
| API acknowledgment latency | < 3 seconds | FastAPI async; immediate Cosmos write |
| Provisioning lead time | < 10 minutes | Automated async workflow |
| Platform availability | ≥ 99.9% | Container Apps + Cosmos DB SLAs |
| Provisioning success rate | ≥ 98% | Retry with exponential backoff + circuit breaker |
| Security | Zero embedded secrets | Key Vault + managed identity |
| Compliance | 100% tagging + Purview registration | Governance stage mandatory before `COMPLETE` |

---

## ROI at a Glance

| | Value |
|---|---|
| Annual cost (status quo) | $500,000 |
| Annual cost (with platform) | $75,000 |
| **Net annual savings** | **$425,000 (85%)** |
| One-time build investment | $80,000 (already complete) |
| **ROI Year 1** | **781% (8.8× return)** |

---

## Project Status

| Phase | Status |
|---|---|
| Core platform (API + worker + shared lib + local backends) | ✅ Complete |
| Azure backend integration (Cosmos, Storage, Event Grid, Key Vault) | ✅ Complete |
| Governance workflow (Purview, tagging, classification) | ✅ Complete |
| Tests | ✅ Complete |
| Observability & alerting (Azure Monitor, App Insights) | ⏳ In progress |
| Production deployment (Bicep / Container Apps) | Not started |
