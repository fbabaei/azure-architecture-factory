# MDR Arrangement Extraction Agent - Architecture Overview

## Purpose
Phase 1 of the EY Tax MDR (Mandatory Disclosure Rules) compliance agent:
ingest unstructured arrangement documents (PDF, text), extract a
structured `MDRArrangement` JSON payload, and drive a human-in-the-loop
clarification chat that fills any missing mandatory fields before a
draft arrangement is issued.

This implementation now follows a two-agent target design:
- Chat Agent: user-facing orchestration, intent routing, off-topic guardrail,
  and follow-up prompts.
- Extraction Agent: specialist extraction and structured output generation.

The system supports three feature paths:
- F1: compliance Q&A chat (RAG-ready with retrieval hook).
- F2: document upload to case draft.
- F3: free-text prompt to case draft with missing-field follow-up.

## BRD Requirement Traceability
- **Compliance agent supporting MDR-specific Q&A and arrangement creation**
  -> Container-hosted FastAPI agent fronted by API Management, with
    `/api/chat` intent routing and Q&A handling.
- **File upload-based extraction**
  -> `POST /api/upload` (alias to `POST /arrangements/upload`) -> Blob Storage
    + Document Intelligence layout model -> Azure OpenAI structured extraction.
- **Text prompt-based extraction**
  -> `POST /api/case/from-text` -> Extraction Agent -> clarification loop for
    missing mandatory fields.
- **Interactive, human-in-the-loop chat**
  -> `POST /api/chat` and `POST /arrangements/{id}/chat` +
    `GET /arrangements/{id}/clarifications`, backed by a session store in
    Cosmos DB.
- **Clarification loop for missing mandatory fields**
  -> `clarification_service` scans the draft against `MANDATORY_FIELDS`
     and produces `ClarificationQuestion` prompts for the next missing field.
- **Draft arrangement output in JSON**
  -> `POST /api/case/{id}/confirm` (alias to `POST /arrangements/{id}/draft`)
    returns the finalised
     `MDRArrangement` JSON.
- **Batch / multi-arrangement processing deferred**
  -> No batch endpoints, no queue worker in the diagram - by design.

## Azure Building Blocks
| Concern | Service |
|---------|---------|
| API gateway, JWT validation, rate limiting | Azure API Management |
| Compute for the agent API | Azure Container Apps |
| LLM extraction + clarification generation | Azure OpenAI (gpt-4o) |
| PDF layout / text extraction | Azure AI Document Intelligence |
| Knowledge retrieval (RAG) | Azure AI Search |
| Source document persistence | Azure Blob Storage |
| Arrangement drafts + chat session state | Azure Cosmos DB (serverless) |
| Secrets + config | Azure Key Vault |
| Workload identity | User-assigned Managed Identity |
| Telemetry, metrics, logs | Application Insights + Log Analytics |

All service-to-service auth uses managed identity + RBAC
(`disableLocalAuth: true` on OpenAI, Document Intelligence, Cosmos).

## Network Topology
Phase 1 is deployed on the public network tier as declared in the BRD
options. Production roll-out should migrate to a VNet-integrated
Container Apps environment with private endpoints for Cosmos, Blob,
Key Vault, OpenAI and Document Intelligence.

## Artefact Map
- Detailed architecture document: `docs/detailed-architecture.md`.
- Overview diagram: `diagrams/mdr-support-20260416174652.drawio`.
- Detailed architecture diagram: `diagrams/mdr-support-20260416174652-detailed-architecture.drawio`.
- Infrastructure: `infra/main.bicep`.
- Source: `src/mdr_agent/`.

## Target State Notes
- Model target can be switched by deployment to GPT-5.2-compatible
  deployments while preserving the current API contract.
- Document pipeline supports optional Content Understanding in a future
  iteration; current implementation keeps the direct Document Intelligence +
  LLM extraction path.
