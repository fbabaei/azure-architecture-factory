# Traceability Matrix

| ID | BRD Requirement | Generated Artifact(s) | Status | Validation Approach |
|---|---|---|---|---|
| REQ-001 | Intake claims documents from partner systems | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-002 | Classify and route claims for review | Governance model — `docs/governance-model.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-003 | Expose an operations API and dashboard | Starter API — `src/copilot_api/main.py`; Architecture overview — `docs/architecture-overview.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-004 | Enable AI-assisted reviewer copilot experience | Governance model — `docs/governance-model.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-005 | Ingest claims payloads via API | Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-006 | Persist claim records and attachments | Architecture overview + extend Bicep for data resources | Pending Extension | Extend generated tests; link test case to this requirement |
| REQ-007 | Provide reviewer workflows and status tracking | Governance model — `docs/governance-model.md` | Pending Extension | Extend generated tests; link test case to this requirement |
| REQ-008 | Surface AI assistance for claim summarization and next-best-action | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-009 | Support operational reporting endpoints | Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-010 | 99.9% service availability | Architecture diagram — `diagrams/<slug>.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-011 | Secure identity and secret handling | Bicep infra — `infra/main.bicep` (Identity & RBAC) | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-012 | Centralized observability and tracing | Architecture overview — `docs/architecture-overview.md`; Deployment guide — `docs/deploy.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-013 | Infrastructure as code with Bicep | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/copilot_api/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-014 | Use managed identities wherever possible | Bicep infra — `infra/main.bicep` (Identity & RBAC) | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-015 | Use Key Vault for secrets and keys | Bicep infra — `infra/main.bicep` (Identity & RBAC) | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| SC-001 | **Success:** A new project is generated end-to-end | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-002 | **Success:** The new drawio diagram contains Azure icon image styles | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |
| SC-003 | **Success:** Generated tests pass in the scaffolded project | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |

## Coverage Summary

| Status | Count | Share |
|---|---|---|
| ✅ Scaffolded | 13 | 87% |
| 🔧 Pending Extension | 2 | 13% |
| 🔍 Review Required | 0 | 0% |

> **Next step**: Invoke the `project-traceability-advisor` agent to produce a full
> requirement → code → test → infrastructure coverage report and update `project-manifest.json`.
