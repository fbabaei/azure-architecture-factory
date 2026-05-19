# Traceability Matrix

| ID | BRD Requirement | Generated Artifact(s) | Status | Validation Approach |
|---|---|---|---|---|
| REQ-001 | The EY Tax team is looking to build a compliance agent to support Mandatory Disclosure Rules (MDR) arrangement creation. The goal is to deliver an agent that enables MDR‑specific Q&A and supports two arrangement‑creation flows: | Deployment guide — `docs/deploy.md`; Governance model — `docs/governance-model.md` | Review Required | Assign acceptance owner; verify generated artifact covers intent |
| REQ-002 | File upload–based extraction | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/mdr_support/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-003 | An interactive, human‑in‑the‑loop chat experience that guides users through creating an arrangement. | Architecture overview — `docs/architecture-overview.md`; Starter API — `src/mdr_support/main.py` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| REQ-004 | This CodeWith will focus on Phase 1, building a data extraction agent capable of ingesting unstructured documents (PDFs and text inputs), extracting structured MDR arrangement data into a consistent JSON format, and enabling an intelligent clarification loop. The agent will identify missing mandatory fields and prompt the user for additional inputs before generating an arrangement draft. | Architecture overview + extend Bicep for data resources | Pending Extension | Extend generated tests; link test case to this requirement |
| REQ-005 | The outcome will be a more reliable, scalable, and user‑friendly arrangement creation workflow, with batch and multi‑arrangement processing explicitly deferred to a later phase. | Deployment guide — `docs/deploy.md` | Pending Extension | Extend generated tests; link test case to this requirement |
| REQ-006 | This engagement will also produce a clear technical blueprint, reusable extraction patterns, and testable end‑to‑end flows that EY can extend into their MDR modernization roadmap and also while significantly reducing the manual time and effort required per document for arrangement creation and review. | Deployment guide — `docs/deploy.md`; Governance model — `docs/governance-model.md` | Scaffolded | Assign acceptance owner; verify generated artifact covers intent |
| SC-001 | **Success:** Generated starter solution is reviewed and refined before production deployment | Success criteria — `docs/success-criteria.md` | Review Required | Assign owner; establish baseline metric before go-live |

## Coverage Summary

| Status | Count | Share |
|---|---|---|
| ✅ Scaffolded | 3 | 50% |
| 🔧 Pending Extension | 2 | 33% |
| 🔍 Review Required | 1 | 17% |

> **Next step**: Invoke the `project-traceability-advisor` agent to produce a full
> requirement → code → test → infrastructure coverage report and update `project-manifest.json`.
