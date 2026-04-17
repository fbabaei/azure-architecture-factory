# Mdr Support

Generated from BRD `mdr-support.md` by the Azure-native factory runner.

## What Was Generated
- `docs/architecture-overview.md`
- `docs/detailed-architecture.md`
- `docs/governance-model.md`
- `docs/delivery-milestones.md`
- `docs/success-criteria.md`
- `docs/traceability-matrix.md`
- `diagrams/mdr-support-20260416174652.md`
- `diagrams/mdr-support-20260416174652.drawio`
- `diagrams/mdr-support-20260416174652-detailed-architecture.md`
- `diagrams/mdr-support-20260416174652-detailed-architecture.drawio`
- `src/copilot_api/main.py`
- `src/copilot_api/models.py`
- `src/copilot_api/services/copilot_service.py`
- `requirements.txt`
- `infra/main.bicep`
- `tests/test_generated_project.py`

## Selected Generation Options
- Monitoring and observability wiring requested: No

## BRD Requirement Highlights
- The EY Tax team is looking to build a compliance agent to support Mandatory Disclosure Rules (MDR) arrangement creation. The goal is to deliver an agent that enables MDR‑specific Q&A and supports two arrangement‑creation flows:
- File upload–based extraction
- An interactive, human‑in‑the‑loop chat experience that guides users through creating an arrangement.
- This CodeWith will focus on Phase 1, building a data extraction agent capable of ingesting unstructured documents (PDFs and text inputs), extracting structured MDR arrangement data into a consistent JSON format, and enabling an intelligent clarification loop. The agent will identify missing mandatory fields and prompt the user for additional inputs before generating an arrangement draft.
- The outcome will be a more reliable, scalable, and user‑friendly arrangement creation workflow, with batch and multi‑arrangement processing explicitly deferred to a later phase.
- This engagement will also produce a clear technical blueprint, reusable extraction patterns, and testable end‑to‑end flows that EY can extend into their MDR modernization roadmap and also while significantly reducing the manual time and effort required per document for arrangement creation and review.
