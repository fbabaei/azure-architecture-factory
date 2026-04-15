# Traceability Matrix

| ID | BRD Requirement | Generated Artifact(s) | Status | Validation Approach |
|---|---|---|---|---|
| REQ-001 | Average response time 4–6 hours due to mis-routing | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-002 | 22% first-visit failure rate — technicians arrive without correct parts or skills | Deployment guide — `docs/deploy.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-003 | No SLA tracking per work-order type | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-004 | 35% of field dispatches are reactive emergency calls that could have been predicted | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-005 | High parts cost due to unplanned failure events | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-006 | Customer SLA penalties for unplanned downtime | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-007 | Average resolution time 2.1× higher for unfamiliar asset types | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-008 | Knowledge concentrated in senior technicians — no knowledge transfer path | Deployment guide — `docs/deploy.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-009 | Customer satisfaction (CSAT) scoring 12 points below industry benchmark | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-010 | GDPR and SOC 2 exposure for customer PII in work records | Governance model — `docs/governance-model.md` | Review Required | Assign acceptance owner; verify generated artifact covers intent |
| REQ-011 | No audit trail for who accessed or updated a work order | Bicep infra — `infra/main.bicep` (Identity & RBAC); Governance model — `docs/governance-model.md` | Review Required | Assign acceptance owner; verify generated artifact covers intent |
| REQ-012 | Shared service credentials create blast-radius risk | Architecture diagram — `diagrams/<slug>.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-013 | MTTR for cross-service failures exceeds 3 hours | Architecture diagram — `diagrams/<slug>.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-014 | No SLA measurement or alerting on dispatch or resolution time | Architecture overview — `docs/architecture-overview.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-015 | Operations team is reactive | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| SC-001 | **Success:** Work-order API accepts, validates, and routes a new work order in under 500 ms end-to-end | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-002 | **Success:** IoT telemetry is ingested, scored, and anomaly alerts are raised within 60 seconds of receipt | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-003 | **Success:** Copilot AI recommendation endpoint returns a structured next-action response in under 2 seconds | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-004 | **Success:** Approval workflow triggers escalation notification within 30 seconds of SLA breach threshold | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-005 | **Success:** All secrets are sourced from Key Vault; zero hard-coded credentials in repository or manifests | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-006 | **Success:** All services authenticate via Managed Identity; no service principal passwords in use | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |

## Coverage Summary

| Status | Count | Share |
|---|---|---|
| ✅ Scaffolded | 13 | 87% |
| 🔧 Pending Extension | 0 | 0% |
| 🔍 Review Required | 2 | 13% |

> **Next step**: Invoke the `project-traceability-advisor` agent to produce a full
> requirement → code → test → infrastructure coverage report and update `project-manifest.json`.
