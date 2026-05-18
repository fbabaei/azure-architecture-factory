# Traceability Matrix

| ID | BRD Requirement | Generated Artifact(s) | Status | Validation Approach |
|---|---|---|---|---|
| REQ-001 | Ingest stock-change events from multiple warehouse systems | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-002 | Fan out updates to e-commerce platform and partner APIs within 5 seconds | Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-003 | Provide an audit log of all inventory changes | Architecture overview — `docs/architecture-overview.md`; Governance model — `docs/governance-model.md` | Review Required | Assign acceptance owner; verify generated artifact covers intent |
| REQ-004 | Support 10,000 events/minute peak throughput | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-005 | Azure-native deployment | Deployment guide — `docs/deploy.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-006 | Managed identity for all service-to-service auth | Bicep infra — `infra/main.bicep` (Identity & RBAC); Architecture diagram — `diagrams/<slug>.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-007 | No public storage endpoints | Starter API — `src/copilot_api/main.py`; Architecture overview + extend Bicep for data resources | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-008 | Private networking preferred | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-009 | Inventory Operations Team | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-010 | E-commerce Engineering | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-011 | Partner Integration Team | Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| SC-001 | **Success:** Generated starter solution is reviewed and refined before production deployment | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |

## Coverage Summary

| Status | Count | Share |
|---|---|---|
| ✅ Scaffolded | 10 | 91% |
| 🔧 Pending Extension | 0 | 0% |
| 🔍 Review Required | 1 | 9% |

> **Next step**: Invoke the `project-traceability-advisor` agent to produce a full
> requirement → code → test → infrastructure coverage report and update `project-manifest.json`.
