# Document Intelligence Agents Step By Step

Use this guide when you are new to Azure AI Agent Foundry and want to learn or build with the Document Intelligence agents.

Primary Microsoft Learn source: <https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/?view=doc-intel-4.0.0>.

## What Was Added

Three Document Intelligence agents were added to the Foundry catalog:

| Agent | Use when | Main output |
| --- | --- | --- |
| Document Intelligence Training Agent | You want to learn Document Intelligence from Microsoft Learn docs, quickstarts, tutorials, Studio concepts, prebuilt models, custom extraction, custom classification, composed models, batch analysis, confidence scores, SDKs, REST API, or responsible AI notes. | Learning path, source references, checkpoint, application follow-up |
| Document Extraction App Agent | You want to design an extraction app for invoices, receipts, forms, IDs, tax/legal/financial documents, layout extraction, custom fields, classifiers, composed models, confidence review, or JSON output contracts. | Model choice, schema, configuration contract, review policy, validation plan |
| Document Knowledge Pipeline Agent | You want to send extracted document content into Azure AI Search, knowledge mining, RAG, metadata enrichment, batch analysis, custom skills, citations, or searchable document workflows. | Extraction-to-index flow, normalized schema, search/RAG contract, citation policy |

These agents work with the existing Document Intelligence Orchestrator and Document Processing App Agent. Use the orchestrator when you are unsure which specialist should own the next step.

## Where To Find Them

Open the local browser catalog:

```text
browser/index.html
```

Search for one of these terms:

- `Document Intelligence`
- `invoice`
- `forms`
- `custom model`
- `RAG`
- `documents`
- `citations`

You can also use these slash prompts from VS Code Chat:

```text
/learn-ai-capability Help me learn Azure AI Document Intelligence for invoices and forms.
```

```text
/design-ai-agent-solution Design a Document Intelligence app that extracts invoice fields and stores reviewed results.
```

## Beginner Flow

Follow this order if you are starting from zero.

### 1. Start With Learning

Ask the learning route to begin with one small step:

```text
/learn-ai-capability Help me learn Azure AI Document Intelligence for invoices and forms.
```

Then ask the specialist to guide you one checkpoint at a time:

```text
Document Intelligence Training Agent, walk me through Azure Document Intelligence from beginner to application-ready. Use the Microsoft Learn docs and local labs. Give me one step at a time with a checkpoint before continuing.
```

Expected output:

1. Matched training topic.
2. Source references.
3. Prerequisites.
4. Step-by-step learning path.
5. Hands-on checkpoint.
6. Application follow-up.
7. Cleanup and cost reminders.
8. Open questions.

Use this agent for questions like:

```text
Document Intelligence Training Agent, teach me prebuilt invoice extraction.
```

```text
Document Intelligence Training Agent, guide me through custom field extraction and composed models.
```

```text
Document Intelligence Training Agent, explain confidence scores, batch analysis, and responsible AI for document processing.
```

### 2. Move From Learning To App Design

When you are ready to design an application, start with the application prompt:

```text
/design-ai-agent-solution Design a Document Intelligence app that extracts invoice fields and stores reviewed results.
```

Expected output:

1. Selected agent blueprints.
2. Input and output contracts.
3. Configuration needs.
4. Integration pattern.
5. Safety and auth considerations.
6. Validation checks.
7. Recommended implementation order.

### 3. Use Document Extraction App Agent For Extraction Apps

Use this agent when the main job is to extract structured fields from documents.

Example:

```text
Document Extraction App Agent, design an invoice and receipt extraction app. It should accept uploaded PDFs, extract vendor, date, subtotal, tax, total, and line items, and send low-confidence fields to human review.
```

Expected output:

1. Extraction app pattern.
2. Model selection rationale.
3. Input contract.
4. Output schema.
5. Configuration contract.
6. Confidence and review policy.
7. Validation plan.
8. Security and privacy notes.
9. Implementation handoff.
10. Missing inputs.

Use it for:

- Invoice extraction.
- Receipt extraction.
- Form extraction.
- ID or tax document extraction.
- Custom field extraction.
- Custom classification.
- Composed model routing.
- Human review for low-confidence fields.

### 4. Use Document Knowledge Pipeline Agent For Search Or RAG

Use this agent when extracted content must become searchable or used for grounded answers.

Example:

```text
Document Knowledge Pipeline Agent, design a searchable policy document pipeline using Document Intelligence and Azure AI Search. Preserve page-level citations and support RAG answers grounded in source documents.
```

Expected output:

1. Pipeline pattern.
2. Extraction-to-index flow.
3. Normalized document schema.
4. Search/RAG contract.
5. Citation and confidence policy.
6. Configuration contract.
7. Validation plan.
8. Monitoring and operations notes.
9. Implementation handoff.
10. Missing inputs.

Use it for:

- Document-to-search indexing.
- Knowledge mining pipelines.
- Searchable metadata enrichment.
- RAG over PDFs or scanned documents.
- Page-level citations.
- Batch document analysis.
- Custom skill bridges.
- Reprocessing and retry workflows.

### 5. Bring In Support Agents

Use these agents when the Document Intelligence design needs more detail:

| Need | Agent |
| --- | --- |
| Endpoint, `.env`, local login, managed identity | Auth Config Agent |
| Data storage, retention, audit records | Data & Storage Design Agent |
| Review queue, exception handling, confidence UX | UX & Human Workflow Agent |
| Sample documents, mocks, acceptance checks | Test & Evaluation Strategy Agent |
| PII, RBAC, threat model, compliance controls | Security & Compliance Agent |
| Responsible AI, privacy, safety review | Responsible AI Safety Agent |
| Azure AI Search indexing and enrichment | Knowledge Mining Search Orchestrator |
| Retrieval, grounding, citations, answer policy | RAG Search App Agent |
| Telemetry, quality signals, alerts | Monitoring & Evaluation Agent |
| Runbooks, rollback, support handoff | Operations Readiness Agent |

### 6. Track The Plan Before Editing Files

Use the planning companion when the design is ready but you do not want code changes yet:

```text
Application Planning Companion Agent, track the implementation steps, owners, open questions, and validation checks for this Document Intelligence app. Do not run commands.
```

Expected output:

1. Current step.
2. Decisions made.
3. Owner agents.
4. Open questions.
5. Validation checks.
6. Next handoff.

### 7. Execute Only Approved Steps

Use the implementation agent only when you have a bounded task that should edit files or run commands:

```text
Application Implementation Validation Agent, execute the approved setup step, edit only the named files, run validation, and summarize evidence.
```

Expected output:

1. Files changed.
2. Commands run.
3. Validation result.
4. Evidence summary.
5. Remaining issues.

## Common Starting Prompts

Learn prebuilt models:

```text
Document Intelligence Training Agent, teach me prebuilt Read, Layout, invoice, and receipt models. Give me checkpoints and application follow-ups.
```

Design extraction:

```text
Document Extraction App Agent, design a form extraction app for customer onboarding packets. Include custom classification, field schema, review policy, and validation plan.
```

Design search/RAG:

```text
Document Knowledge Pipeline Agent, design a document-to-search pipeline for policies and procedures. Include normalized schema, chunking, citations, Azure AI Search fields, and reprocessing policy.
```

Coordinate the whole app:

```text
Azure AI Application Orchestrator, design a complete Document Intelligence solution for uploaded contracts. Route to the right Document Intelligence, search, auth, data, UX, security, and validation agents.
```

## Safety And Grounding Rules

All Document Intelligence agents should follow these rules:

1. Do not invent model IDs, supported fields, confidence thresholds, resource names, endpoints, schemas, or test results.
2. Separate verified facts from assumptions and open questions.
3. Use Microsoft Learn, local lab files, registry entries, command output, or user-provided details as evidence.
4. Do not expose sensitive document contents in summaries unless safe sample data was explicitly provided.
5. Use human review for low-confidence or high-risk document extraction.
6. Preserve citations and source metadata when building search or RAG workflows.

## Quick Decision Guide

| If you want to... | Start with... |
| --- | --- |
| Learn Document Intelligence | Document Intelligence Training Agent |
| Choose the right Document Intelligence route | Document Intelligence Orchestrator |
| Extract fields from documents | Document Extraction App Agent |
| Configure a general document processing blueprint | Document Processing App Agent |
| Build search, knowledge mining, or RAG over documents | Document Knowledge Pipeline Agent |
| Turn the design into a step-by-step plan | Application Planning Companion Agent |
| Edit files and run validation | Application Implementation Validation Agent |
