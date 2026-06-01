# Mdr Support

Generated from BRD `mdr-support.md` by the Azure-native factory runner (.NET specialist).

## Implementation Language

**.NET 8 (ASP.NET Core minimal API, C#)**

## Detected Archetype

**extraction-chat** -- Document extraction + clarification loop + human-in-the-loop chat

## What Was Generated
- `docs/architecture-overview.md`
- `docs/governance-model.md`
- `docs/delivery-milestones.md`
- `docs/success-criteria.md`
- `docs/traceability-matrix.md`
- `docs/detailed-architecture.md`
- `diagrams/mdr-support-20260421003634.md`
- `diagrams/mdr-support-20260421003634.drawio`
- `src/MdrSupport.csproj`
- `src/Program.cs`
- `src/Models.cs`
- `src/Services/DocumentIngestionService.cs`
- `src/Services/ExtractionService.cs`
- `src/Services/ClarificationService.cs`
- `src/Services/DraftRepository.cs`
- `src/Services/SessionService.cs`
- `src/appsettings.json`
- `src/appsettings.Development.json`
- `src/Dockerfile`
- `src/.dockerignore`
- `tests/MdrSupport.Tests.csproj`
- `tests/HealthEndpointTests.cs`
- `global.json`
- `sample-corpus/README.md`
- `sample-corpus/manifest.json`

## Selected Generation Options
- Monitoring and observability wiring requested: Yes

## BRD Requirement Highlights
- The EY Tax team is looking to build a compliance agent to support Mandatory Disclosure Rules (MDR) arrangement creation. The goal is to deliver an agent that enables MDR‑specific Q&A and supports two arrangement‑creation flows:
- File upload–based extraction
- An interactive, human‑in‑the‑loop chat experience that guides users through creating an arrangement.
- This CodeWith will focus on Phase 1, building a data extraction agent capable of ingesting unstructured documents (PDFs and text inputs), extracting structured MDR arrangement data into a consistent JSON format, and enabling an intelligent clarification loop. The agent will identify missing mandatory fields and prompt the user for additional inputs before generating an arrangement draft.
- The outcome will be a more reliable, scalable, and user‑friendly arrangement creation workflow, with batch and multi‑arrangement processing explicitly deferred to a later phase.
- This engagement will also produce a clear technical blueprint, reusable extraction patterns, and testable end‑to‑end flows that EY can extend into their MDR modernization roadmap and also while significantly reducing the manual time and effort required per document for arrangement creation and review.
