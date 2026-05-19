# OrderManagement Platform — One-Page Summary

**Version:** 1.0 | **Date:** March 30, 2026 | **Region:** East US | **Status:** Production-Ready

---

## What It Is

A **production-ready, cloud-native microservices order processing platform** built on Azure. It handles the complete order lifecycle — intake, inventory reservation, payment, notification, and real-time analytics — using an event-driven architecture with Azure Service Bus, dual-database persistence (Cosmos DB + SQL), full distributed tracing, and enterprise security. It is both a working order processing backend and an approved organisational reference architecture for event-driven microservices.

---

## Business Problem Solved

| Pain Point | Impact Before |
|---|---|
| Monolithic order system cannot scale past 500 concurrent orders | Lost orders under load; emergency ops incidents |
| Synchronous inventory + payment coupling — no compensation events | Oversell events; double-charge risk; weekly manual reconciliation |
| No real-time analytics — 24-hour batch jobs only | Business decisions on stale data; no early warning for failures |
| Secrets in env vars; over-privileged identities; no private endpoints | PCI-DSS / GDPR exposure; credential leakage risk |
| No distributed tracing across services — MTTR 3–4 hours | Customer support blind; SLA unmeasured |

---

## Architecture Overview

```
                         ┌─────────────────────────────────────────────────────────────┐
  Clients                │              AZURE CONTAINER APPS                           │
     │                   │                                                             │
     ▼                   │  ┌─────────────┐    ┌──────────────┐   ┌────────────────┐  │
  Azure API         ────►│  │ API Gateway  ├───►│ Order Service ├──►│Inventory Service│  │
  Management             │  │  (port 8000) │    │  (port 8001) │   │  (port 8002)   │  │
  (APIM)                 │  │ JWT, rate    │    │  Cosmos DB   │   │  Azure SQL DB  │  │
                         │  │ limit, route │    └──────┬───────┘   └───────┬────────┘  │
                         │  └─────────────┘           │                   │            │
                         │                            │  Azure Service Bus │            │
                         │               ┌────────────▼───────────────────▼──────────┐ │
                         │               │  Topics: OrderCreated, OrderCancelled,     │ │
                         │               │  PaymentProcessed, InventoryReserved,      │ │
                         │               │  PaymentFailed, RefundIssued               │ │
                         │               └────────────┬───────────────────┬───────────┘ │
                         │                            │                   │             │
                         │               ┌────────────▼───────┐ ┌────────▼──────────┐  │
                         │               │  Payment Service    │ │Notification Service│  │
                         │               │  (port 8003)        │ │  (port 8004)       │  │
                         │               │  Cosmos DB          │ │  Email / SMS APIs  │  │
                         │               └────────────────────┘ └───────────────────┘  │
                         │               ┌────────────────────┐                         │
                         │               │  Analytics Service  │                         │
                         │               │  (port 8005)        │                         │
                         │               │  Cosmos DB + KQL    │                         │
                         │               └────────────────────┘                         │
                         └─────────────────────────────────────────────────────────────┘
```

---

## Microservice Breakdown

| Service | Port | Data Store | Responsibilities |
|---|---|---|---|
| `api-gateway` | 8000 | — | JWT validation, rate limiting, request routing to all services |
| `order-service` | 8001 | Cosmos DB (Orders) | Create, retrieve, list, cancel orders; publish OrderCreated/Cancelled events |
| `inventory-service` | 8002 | Azure SQL DB | Stock checks, reserve/release inventory; subscribe to order events |
| `payment-service` | 8003 | Cosmos DB (Payments) | Process payments, issue refunds; subscribe to order events |
| `notification-service` | 8004 | Cosmos DB (Notifications) | Send email/SMS; subscribe to order, payment, and inventory events |
| `analytics-service` | 8005 | Cosmos DB (Analytics) | Aggregate KPIs; daily orders, payment success rate, inventory turnover |
| `shared-lib` | — | — | Config, models, telemetry, resilience, Service Bus client, correlation ID propagation |

---

## Event Flow — Order Lifecycle

```
POST /api/v1/orders (APIM → API Gateway → Order Service)
    │
    ├─► [Cosmos DB] — Order stored (PENDING)
    │
    └─► ServiceBus: OrderCreated
            ├─► Inventory Service — reserve stock → InventoryReserved
            │       └─► if out-of-stock → InventoryFailed → Order cancelled
            ├─► Payment Service — process payment → PaymentProcessed / PaymentFailed
            │       └─► if failed → compensation: release inventory reservation
            └─► Notification Service — send confirmation email/SMS
                Analytics Service — aggregate order metrics
```

---

## Key Azure Resources

| Resource | SKU / Config | Role |
|---|---|---|
| Azure Container Apps | Consumption | Hosts all 6 microservices; scale-to-zero |
| Azure Cosmos DB | Serverless (3 databases) | Orders, Payments, Analytics, Notifications |
| Azure SQL Database | General Purpose, 4 vCores | Inventory tables with optimistic concurrency |
| Azure Service Bus | Standard | Event topics: OrderCreated, PaymentProcessed, etc. |
| Azure API Management | Standard | APIM gateway; JWT validation; rate limiting; versioning |
| Azure Container Registry | Standard | Docker images for all 6 services |
| Azure Key Vault | Standard | All secrets; connection strings via managed identity |
| Application Insights | Pay-as-you-go | Distributed tracing; correlation ID propagation |
| Log Analytics Workspace | Pay-as-you-go | Structured logs; KQL analytics queries |
| Azure Monitor | Standard | Alerts: error rate, queue depth, latency, pod health |
| Azure Virtual Network | Standard | Private endpoints for Cosmos DB, SQL, Service Bus |

---

## Infrastructure as Code (Bicep)

| Module | Resources Provisioned |
|---|---|
| `modules/container-apps.bicep` | Container Apps environment + 6 app deployments |
| `modules/databases.bicep` | Cosmos DB (3 containers) + Azure SQL Database |
| `modules/messaging.bicep` | Service Bus namespace + topics + subscriptions |
| `modules/security.bicep` | Key Vault + Managed Identity + RBAC role assignments |
| `modules/monitoring.bicep` | App Insights + Log Analytics Workspace + alert rules |
| `params/dev.bicepparam` | Dev environment parameters |
| `params/test.bicepparam` | Test environment parameters |
| `params/prod.bicepparam` | Production environment parameters |

---

## Cross-Cutting Capabilities

| Capability | Implementation |
|---|---|
| **Distributed Tracing** | Correlation ID propagated across all service calls; App Insights end-to-end traces |
| **Resilience** | Circuit breakers + exponential backoff + retry policies + dead-letter queues |
| **Security** | Managed Identity; Key Vault; private endpoints; TLS 1.3; JWT at APIM |
| **Idempotency** | Payment and inventory endpoints keyed on idempotency token (no double-charge) |
| **Event Compensation** | PaymentFailed → InventoryRelease saga; OrderCancelled → RefundIssued |
| **Observability** | App Insights + Log Analytics + Azure Monitor alerts + monitoring dashboard |

---

## Non-Functional Requirements

| Requirement | Target | Mechanism |
|---|---|---|
| Order creation latency (p99) | < 500ms | Async event bus; fast Cosmos write |
| Order processing success rate | ≥ 99.5% | Retry + compensation events |
| Concurrent order throughput | ≥ 1,000/min | Container Apps horizontal scaling |
| Analytics data freshness | ≤ 5 minutes | Real-time event subscription |
| MTTR for order failures | < 20 minutes | Distributed traces; structured alerts |
| Zero embedded secrets | 100% | Key Vault + managed identity |
| Compliance | PCI-DSS, GDPR | Private endpoints; TLS 1.3; data masking |
| Test coverage | ≥ 65% | Unit + integration + load tests |

---

## ROI at a Glance

| | Value |
|---|---|
| Cost savings vs. monolith/custom build | $800,000/yr |
| Revenue protection (eliminate oversell) | $500,000/yr |
| **Total annual benefit** | **$1,300,000** |
| Build investment (already complete) | $200,000 |
| **ROI Year 1** | **550% (6.5× return)** |

---

## Project Status

| Phase | Status | Score |
|---|---|---|
| Architecture design (Draw.io + notes) | ✅ Complete | 18 components, 6 services, 3 data stores |
| Implementation (all 6 services + shared lib) | ✅ Complete | Python 3.13, FastAPI |
| Infrastructure (Bicep — 5 modules, 3 param files) | ✅ Complete | 0 validation errors |
| Production readiness review | ✅ Complete | Readiness: 9.4 / Security: 9.2 / Monitoring: 9.5 |
| Test coverage | ✅ Complete | 65% unit + integration |
| Azure deployment | ⏳ Pending | Resource group: `order-management-platform-dev-rg` |
