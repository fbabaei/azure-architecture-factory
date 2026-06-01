# Traceability Matrix

| ID | BRD Requirement | Generated Artifact(s) | Status | Validation Approach |
|---|---|---|---|---|
| REQ-001 | Build an event-driven ingestion and processing pipeline | Deployment guide — `docs/deploy.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-002 | Provide an API layer for inventory, pricing, and replenishment recommendations | Starter API — `src/copilot_api/main.py`; Deployment guide — `docs/deploy.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-003 | Support a web dashboard for operations users | Architecture overview — `docs/architecture-overview.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-004 | Include observability, security, and governance controls by default | Bicep infra — `infra/main.bicep` (Identity & RBAC); Architecture overview — `docs/architecture-overview.md` | Review Required | Assign acceptance owner; verify generated artifact covers intent |
| REQ-005 | Generate architecture diagram, implementation scaffolding, and deployment assets | Deployment guide — `docs/deploy.md`; Architecture diagram — `diagrams/<slug>.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-006 | The system shall ingest store transaction events near real time | Architecture overview + extend Bicep for data resources | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-007 | The system shall persist transactional and aggregated data | Architecture overview + extend Bicep for data resources | Pending Extension | Extend generated tests; link test case to this requirement |
| REQ-008 | The system shall provide REST APIs for inventory and pricing insights | Starter API — `src/copilot_api/main.py`; Architecture overview — `docs/architecture-overview.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-009 | The system shall integrate an AI-assisted operations copilot experience | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-010 | The system shall support role-based access for platform engineers and operations users | Bicep infra — `infra/main.bicep` (Identity & RBAC) | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-011 | Availability target: 99.9% | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-012 | P95 API response time under 300ms for read endpoints | Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-013 | Centralized logging, metrics, and tracing for all services | Architecture overview — `docs/architecture-overview.md`; Deployment guide — `docs/deploy.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-014 | Secrets must be stored in Azure Key Vault | Bicep infra — `infra/main.bicep` (Identity & RBAC); Architecture overview + extend Bicep for data resources | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-015 | Infrastructure must be defined as code using Bicep | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| SC-001 | **Success:** Architecture diagram and companion notes are generated | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-002 | **Success:** A project folder is created with source, tests, docs, and infra | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-003 | **Success:** Generated artifacts are suitable as a starting point for implementation sprints | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-004 | **Success:** The flow completes without manual intervention | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |

## Coverage Summary

| Status | Count | Share |
|---|---|---|
| ✅ Scaffolded | 13 | 87% |
| 🔧 Pending Extension | 1 | 7% |
| 🔍 Review Required | 1 | 7% |

> **Next step**: Invoke the `project-traceability-advisor` agent to produce a full
> requirement → code → test → infrastructure coverage report and update `project-manifest.json`.
