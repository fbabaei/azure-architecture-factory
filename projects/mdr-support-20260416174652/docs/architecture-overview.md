# Mdr Support - Architecture Overview

## Target Architecture
This starter architecture packages the submitted BRD into a generated project scaffold that can be refined for Azure deployment.

## Requirement Signals
- The EY Tax team is looking to build a compliance agent to support Mandatory Disclosure Rules (MDR) arrangement creation. The goal is to deliver an agent that enables MDR‑specific Q&A and supports two arrangement‑creation flows:
- File upload–based extraction
- An interactive, human‑in‑the‑loop chat experience that guides users through creating an arrangement.
- This CodeWith will focus on Phase 1, building a data extraction agent capable of ingesting unstructured documents (PDFs and text inputs), extracting structured MDR arrangement data into a consistent JSON format, and enabling an intelligent clarification loop. The agent will identify missing mandatory fields and prompt the user for additional inputs before generating an arrangement draft.
- The outcome will be a more reliable, scalable, and user‑friendly arrangement creation workflow, with batch and multi‑arrangement processing explicitly deferred to a later phase.
- This engagement will also produce a clear technical blueprint, reusable extraction patterns, and testable end‑to‑end flows that EY can extend into their MDR modernization roadmap and also while significantly reducing the manual time and effort required per document for arrangement creation and review.

## Recommended Building Blocks
- Presentation or workflow entry point
- Integration API layer
- Data or document store
- Observability with Application Insights and Log Analytics
- Identity, secrets, and governance controls

## Network Topology
- **Network Tier**: Public (internet-facing, no VNet isolation)

## Capability Coverage
- Azure OpenAI: Not explicitly requested
- Microsoft Copilot: Not explicitly requested
- Machine Learning lifecycle: Not explicitly requested
- Governance controls: Yes
