# Field Service Intelligence Platform

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Date** | April 15, 2026 |
| **Status** | APPROVED |
| **Prepared For** | Engineering Leadership, Field Operations, Cloud Platform |
| **Sponsor** | VP of Operations |
| **Primary Region** | East US 2 |
| **Network Tier** | private |

---

## 1. Executive Summary

The **Field Service Intelligence Platform** is a cloud-native Azure solution that digitises and automates field technician dispatch, work-order lifecycle management, real-time telemetry from IoT-enabled assets, and AI-assisted next-action recommendations for service teams.

It demonstrates enterprise-grade patterns across the full Azure Architecture Factory capability matrix: event-driven async messaging, copilot-assisted workflows, governance via Key Vault and Managed Identity, private-network isolation, and end-to-end observability with Application Insights.

This BRD is designed to exercise all major factory capabilities and produce a fully traced, end-to-end generated project: architecture diagram, API scaffold, Bicep infrastructure, traceability matrix, governance model, delivery milestones, and success criteria.

---

## 2. Business Problem Statement

### 2.1 Uncoordinated Dispatch and Work-Order Routing

**Problem:** Service technicians are assigned work orders through a legacy queue with no real-time visibility into technician location, skill set, or asset history.

**Impact:**
- Average response time 4–6 hours due to mis-routing
- 22% first-visit failure rate — technicians arrive without correct parts or skills
- No SLA tracking per work-order type

**Root Cause:** No routing engine consuming real-time technician and asset signals.

---

### 2.2 No Asset Telemetry or Predictive Maintenance

**Problem:** IoT-enabled assets (HVAC, elevators, industrial equipment) emit telemetry but no pipeline ingests, processes, or stores it for anomaly detection or predictive maintenance scoring.

**Impact:**
- 35% of field dispatches are reactive emergency calls that could have been predicted
- High parts cost due to unplanned failure events
- Customer SLA penalties for unplanned downtime

**Root Cause:** No event-driven IoT ingestion pipeline connected to a machine-learning scoring endpoint.

---

### 2.3 AI Assistance Not Available at Point of Work

**Problem:** Technicians in the field rely on paper manuals and phone calls to resolve unfamiliar faults. No copilot experience provides real-time summarisation, fault-code lookup, or recommended actions.

**Impact:**
- Average resolution time 2.1× higher for unfamiliar asset types
- Knowledge concentrated in senior technicians — no knowledge transfer path
- Customer satisfaction (CSAT) scoring 12 points below industry benchmark

**Root Cause:** AI capabilities (Azure OpenAI, Cognitive Services) are not integrated into the field service workflow or mobile client API.

---

### 2.4 Security, Compliance, and Audit Gaps

**Problem:** Work-order data contains PII (customer address, contact details) and sensitive asset configurations. Secrets are hard-coded in deployment manifests; access audit logs do not exist.

**Impact:**
- GDPR and SOC 2 exposure for customer PII in work records
- No audit trail for who accessed or updated a work order
- Shared service credentials create blast-radius risk

**Root Cause:** Security is not enforced at the platform level — no Key Vault, no Managed Identity, no policy guardrails.

---

### 2.5 Observability Blind Spots

**Problem:** There is no distributed trace linking a field technician's API call through dispatch, IoT scoring, and AI recommendation to the final work-order update. Failures surface as customer complaints, not alerts.

**Impact:**
- MTTR for cross-service failures exceeds 3 hours
- No SLA measurement or alerting on dispatch or resolution time
- Operations team is reactive

**Root Cause:** No Application Insights telemetry, no log-correlation strategy, no alerting rules.

---

## 3. Scope

### 3.1 In Scope

- Technician and work-order management API (REST endpoint, API Management gateway)
- IoT asset telemetry ingestion via Event Hubs with stream processing
- Machine learning scoring endpoint for predictive maintenance signals
- Azure OpenAI / Copilot-assisted fault resolution and next-best-action recommendations
- Approval and escalation workflow (automated routing with human-in-the-loop approval steps)
- Integration with external ERP and parts-inventory systems via API
- Private VNet with private endpoints for all data plane services
- Key Vault for all secrets, connection strings, and certificates
- Managed Identity for all service-to-service authentication
- Azure Policy guardrails for compliance enforcement
- Application Insights distributed tracing across all services
- Alert rules for dispatch SLA breach, anomaly detection threshold, and API error rates

### 3.2 Out of Scope

- Mobile client application UI (API surface only)
- Legacy system decommissioning
- On-premises connectivity beyond existing VPN
- Third-party payment processing

---

## 4. Functional Requirements

- Expose a field service API that accepts and routes work orders in real time
- Ingest IoT telemetry from registered assets via Event Hubs
- Score ingested telemetry against a machine learning anomaly detection model
- Surface AI-assisted fault summaries and next-action recommendations to technicians via copilot API
- Implement approval workflow for high-priority or high-cost work orders
- Integrate with external ERP via REST endpoint to sync parts inventory and work-order status
- Persist all work-order records, asset telemetry, and audit events in a governed data store
- Enforce authentication and authorisation via Managed Identity and API Management policies
- Store all secrets in Key Vault with no hard-coded credentials anywhere in the codebase
- Apply Azure Policy compliance governance to all provisioned resources
- Emit distributed traces from every service boundary into Application Insights
- Trigger alert notifications for SLA breach, error rate spike, and anomaly score threshold

---

## 5. Non-Functional Requirements

- API response time: p95 < 300 ms for work-order read; p95 < 800 ms for AI-assisted recommendation
- Availability: 99.9% monthly uptime for the dispatch API
- Data residency: All data must remain within East US 2 region
- Network: All data-plane traffic must traverse private endpoints; no public internet exposure for storage or database
- Compliance: GDPR, SOC 2 Type II alignment required for PII fields
- Scalability: Support 5 000 active technicians and 50 000 work-order events per day at launch

---

## 6. Azure Architecture Components

The following Azure services are required:

- **Azure API Management** — unified API gateway for all external and internal consumers
- **Azure Container Apps** — microservices for dispatch engine, copilot API, and workflow orchestrator
- **Azure OpenAI Service** — GPT-4 powered fault summarisation and next-best-action copilot
- **Azure Cognitive Services** — vision and language capabilities for asset image analysis
- **Azure Event Hubs** — high-throughput IoT telemetry ingestion
- **Azure Machine Learning** — predictive maintenance scoring endpoint
- **Azure Cosmos DB** — globally consistent work-order and asset record store
- **Azure SQL** — relational work-order history and audit log
- **Azure Service Bus** — reliable async messaging for approval workflows and ERP integration
- **Azure Logic Apps** — approval and escalation workflow orchestration
- **Azure Key Vault** — secrets, certificates, and connection-string management
- **Managed Identity** — service-to-service auth; no service principal passwords
- **Azure Virtual Network** — private subnet isolation with private endpoints
- **Network Security Groups** — ingress/egress rules per subnet
- **Azure Policy** — compliance guardrails for resource configuration
- **Application Insights** — distributed tracing, metrics, and alerting
- **Log Analytics Workspace** — centralised log aggregation
- **Azure Monitor** — dashboards and alert rule management

---

## 7. Success Criteria

- Work-order API accepts, validates, and routes a new work order in under 500 ms end-to-end
- IoT telemetry is ingested, scored, and anomaly alerts are raised within 60 seconds of receipt
- Copilot AI recommendation endpoint returns a structured next-action response in under 2 seconds
- Approval workflow triggers escalation notification within 30 seconds of SLA breach threshold
- All secrets are sourced from Key Vault; zero hard-coded credentials in repository or manifests
- All services authenticate via Managed Identity; no service principal passwords in use
- Application Insights shows end-to-end distributed trace for every work-order API call
- Azure Policy compliance score is 100% for all provisioned resources
- Generated project passes the factory validation suite with no critical findings

---

## 8. Delivery Milestones

| Milestone | Description | Target |
|---|---|---|
| M1 | Factory project generation and architecture diagram | Day 0 (automated) |
| M2 | Bicep infrastructure deployed to dev environment | Week 1 |
| M3 | Dispatch API and copilot API scaffold deployed and health-checked | Week 2 |
| M4 | IoT telemetry pipeline and ML scoring endpoint live | Week 3 |
| M5 | Approval workflow and ERP integration tested | Week 4 |
| M6 | Observability dashboards and alert rules active | Week 5 |
| M7 | Security review: Key Vault, Managed Identity, Policy compliance | Week 6 |
| M8 | Production readiness review and sign-off | Week 7 |

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Azure OpenAI quota insufficient at launch scale | Medium | High | Pre-request quota increase; use Provisioned Throughput Units |
| IoT telemetry volume exceeds Event Hubs throughput units | Low | High | Auto-inflate enabled; capacity alerts set at 70% threshold |
| Private endpoint DNS resolution configuration complexity | Medium | Medium | Use Azure Private DNS Zones; validate with factory Bicep module |
| ML model accuracy below threshold at launch | Low | Medium | Shadow-mode scoring initially; gate on A/B evaluation results |

---

## 10. Approvals

| Role | Name | Status |
|---|---|---|
| Engineering Lead | — | Approved |
| Security & Compliance | — | Approved |
| Cloud Platform | — | Approved |
| VP Operations (Sponsor) | — | Approved |
