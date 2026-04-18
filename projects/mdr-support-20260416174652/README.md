# MDR Arrangement Extraction Agent

EY Tax — Mandatory Disclosure Rules (MDR) compliance agent, Phase 1.

Built from BRD [`docs/intake/mdr-support.md`](../../docs/intake/mdr-support.md)
by the Azure-native factory runner and then hand-refined to match the BRD
intent: a data-extraction agent that ingests PDFs/text, produces a
structured JSON arrangement, and drives a human-in-the-loop clarification
chat until every mandatory field is captured.

The implementation now aligns to the Compliance Intelligence Agent technical
design with:
- Two-agent runtime split (Chat Orchestrator Agent + Extraction Specialist Agent).
- Three feature routes: Q&A chat, document upload to draft, and text prompt
  to draft.
- Hybrid RAG support in the Q&A path using semantic + vector retrieval when
  a vector-capable Azure AI Search index is provisioned.
- Session lifecycle APIs under `/api/session/*` and case APIs under
  `/api/case/*`.
- Off-topic guardrail in `/api/chat` for non-compliance prompts.

## What is generated
- `src/mdr_agent/main.py` — FastAPI app (upload, extract, chat, draft).
- `src/mdr_agent/models.py` — Pydantic schema for MDR arrangements.
- `src/mdr_agent/services/agent_runtime.py` — logical Chat + Extraction agent runtime.
- `src/mdr_agent/services/document_ingestion.py` — Blob Storage + Document Intelligence.
- `src/mdr_agent/services/extraction_agent.py` — Azure OpenAI structured extraction.
- `src/mdr_agent/services/clarification_service.py` — Missing-field detection + prompts.
- `src/mdr_agent/services/chat_session.py` — Human-in-the-loop state machine.
- `src/mdr_agent/services/repository.py` — Cosmos DB persistence (with in-memory fallback).
- `infra/main.bicep` — Container Apps, APIM, OpenAI, Document Intelligence,
  AI Search, Blob, Cosmos, Key Vault, Managed Identity, App Insights,
  Log Analytics.
- `diagrams/mdr-support-20260416174652.drawio` — Overview diagram.
- `diagrams/mdr-support-20260416174652-detailed-architecture.drawio` — Detailed
  architecture, flows, and network view.
- `docs/` — architecture, traceability, governance, milestones, success criteria.
- `tests/test_generated_project.py` — smoke tests for the extraction and chat loop.
- `scripts/bootstrap_search_index.py` — creates and seeds the vector-capable search index.
- `scripts/run_search_index.ps1` — PowerShell helper that can resolve deployment outputs and run indexing.
- `sample-corpus/` — small MDR reference corpus and manifest for immediate RAG bootstrap demos.

## Run locally
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn mdr_agent.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

The agent auto-falls back to an in-memory repository and a heuristic
extractor when Azure OpenAI / Blob / Cosmos endpoints are not configured,
so the end-to-end upload + chat + draft flow works offline for tests.

## Bootstrap the MDR knowledge base
After Azure deployment, the quickest path is the PowerShell wrapper. It defaults to the checked-in sample corpus and can pull the Azure AI Search and Azure OpenAI endpoints from the latest successful deployment in your resource group.

```powershell
.\scripts\run_search_index.ps1 -ResourceGroupName rg-mdr-support-dev
```

Useful variations:

```powershell
# Create or update the index schema without uploading documents.
.\scripts\run_search_index.ps1 -ResourceGroupName rg-mdr-support-dev -CreateOnly

# Point at a different corpus or explicit endpoints.
.\scripts\run_search_index.ps1 `
  -SearchEndpoint "https://<search>.search.windows.net" `
  -OpenAIEndpoint "https://<openai>.openai.azure.com/" `
  -SourceDir .\sample-corpus
```

The underlying Python CLI is still available when you want full control:

```powershell
python .\scripts\bootstrap_search_index.py --manifest .\sample-corpus\manifest.json `
  --search-endpoint "https://<search>.search.windows.net" `
  --openai-endpoint "https://<openai>.openai.azure.com/"
```

## API surface (design-aligned)
- `POST /api/session` — create session.
- `GET /api/session/{id}` — retrieve session history and current draft state.
- `DELETE /api/session/{id}` — clear session and draft.
- `POST /api/chat` — intent-routed chat endpoint (Q&A, clarification, off-topic guardrail).
- `POST /api/upload` — upload file and extract first draft.
- `POST /api/case/from-text` — create first draft from free text.
- `GET /api/case/{id}` — get current draft.
- `PUT /api/case/{id}` — user edits draft.
- `POST /api/case/{id}/confirm` — finalize draft when mandatory fields are complete.

## BRD requirement highlights
- Compliance agent supporting **MDR-specific Q&A and arrangement creation**.
- **File upload-based extraction** of unstructured PDFs / text into JSON.
- **Interactive, human-in-the-loop chat** to resolve missing mandatory fields.
- **Clarification loop** that identifies missing fields and prompts the user.
- Batch / multi-arrangement processing is **explicitly deferred** to a later phase.
