# Reconfigurable Agents

Reconfiguration means an agent is not a fixed one-scenario template. It is a reusable baseline that starts with common Azure AI patterns, then adapts its configuration contract to the user's requirements.

In this repo, the Azure AI Search prebuilt reconfigurable category uses one router and three specialized configurable agents:

- Azure AI Search Reconfigurable Orchestrator
- Classic Search Reconfigurable Agent
- RAG Search Reconfigurable Agent
- Agentic Retrieval Reconfigurable Agent

The document processing prebuilt reconfigurable category adds two specialized configurable agents:

- Document Intelligence Reconfigurable Agent
- Document-to-Search Pipeline Reconfigurable Agent

The cross-modal and guardrail prebuilt reconfigurable category adds three specialized configurable agents:

- Multimodal Knowledge Pipeline Reconfigurable Agent
- Speech & Conversation Intelligence Reconfigurable Agent
- Responsible AI Guardrail Reconfigurable Agent

The quality, workflow, and human review prebuilt reconfigurable category adds three specialized configurable agents:

- AI Evaluation & Quality Reconfigurable Agent
- Tool-Using Workflow Reconfigurable Agent
- Human Review & Escalation Reconfigurable Agent

The lifecycle and governance prebuilt reconfigurable category adds three specialized configurable agents:

- Knowledge Freshness & Reindexing Reconfigurable Agent
- Observability & Continuous Improvement Reconfigurable Agent
- Cost & Capacity Governance Reconfigurable Agent

For a step-by-step user manual with starter prompts, examples, handoffs, and validation checks, see [Reconfigurable Agents Quick Start](reconfigurable-agents-quick-start.md). For an end-to-end mock project example, see [Reconfigurable Agents Walkthrough](reconfigurable-agents-walkthrough.md).

## How Reconfiguration Works

1. The user starts with Azure AI Search Reconfigurable Orchestrator.
2. The orchestrator decides whether the request is classic search, RAG search, agentic retrieval, mixed, evaluation/quality, tool workflow, human review, freshness/reindexing, observability/improvement, cost/capacity, or missing enough detail.
3. The orchestrator extracts a shared requirements profile.
4. The orchestrator routes to the most specific reconfigurable agent.
5. The selected agent starts from its baseline capabilities and fills in the relevant reconfiguration points.
6. The selected agent returns missing inputs, special-case handling, validation checks, and handoffs.

The router captures this shared profile:

```text
USER_OUTCOME
DATA_SOURCES
SOURCE_FRESHNESS
RETRIEVAL_PATTERN
SECURITY_MODEL
GROUNDING_POLICY
VALIDATION_PLAN
```

## Classic Search Reconfiguration

Classic search reconfiguration is for direct index-first Azure AI Search experiences. Use it when the application primarily returns ranked results instead of generated answers.

The Classic Search Reconfigurable Agent adapts these points:

```text
SEARCH_ENDPOINT
SEARCH_INDEX
DATA_SOURCES
INGESTION_MODE
INDEX_SCHEMA
QUERY_FEATURES
RELEVANCE_POLICY
SECURITY_MODEL
SPECIAL_CASES
VALIDATION_PLAN
```

For example, if the user needs product catalog search with filters, facets, autocomplete, region-based access, and relevance tuning, the agent configures itself around direct index-first search, not RAG or agentic retrieval.

## RAG Search Reconfiguration

RAG search reconfiguration is for applications that retrieve content from Azure AI Search and then own prompt assembly, answer generation, citations, and no-answer behavior.

The RAG Search Reconfigurable Agent adapts these points:

```text
SEARCH_ENDPOINT
SEARCH_INDEX
DATA_SOURCES
CHUNKING_POLICY
RETRIEVAL_MODE
EMBEDDING_DEPLOYMENT
PROMPT_ASSEMBLY
GROUNDING_POLICY
SECURITY_MODEL
SPECIAL_CASES
VALIDATION_PLAN
```

For example, if the user needs grounded generated answers with citations, chunking, hybrid retrieval, and unsupported-question behavior, the agent adapts around retrieval plus prompt assembly.

## Agentic Retrieval Reconfiguration

Agentic retrieval reconfiguration is for scenarios where Azure AI Search should manage retrieval through knowledge bases and knowledge sources.

The Agentic Retrieval Reconfigurable Agent adapts these points:

```text
SEARCH_ENDPOINT
KNOWLEDGE_BASE
KNOWLEDGE_SOURCES
SOURCE_MODE
SOURCE_FRESHNESS
RETRIEVAL_REASONING_EFFORT
QUERY_PLANNING_MODE
ANSWER_SYNTHESIS
MODEL_DEPLOYMENT
GROUNDING_POLICY
SECURITY_MODEL
SPECIAL_CASES
VALIDATION_PLAN
```

For example, if the user needs Azure AI Search to manage knowledge bases, knowledge sources, query decomposition, references, activity logs, and optional synthesis, the agent configures the agentic retrieval baseline.

## Document Intelligence Reconfiguration

Document Intelligence reconfiguration is for structured extraction workflows where the output is an explicit document schema, JSON contract, review queue, or downstream business record.

The Document Intelligence Reconfigurable Agent adapts these points:

```text
DOCUMENT_INTELLIGENCE_ENDPOINT
DOCUMENT_INTELLIGENCE_AUTH_MODE
DOCUMENT_TYPES
DOCUMENT_SOURCES
EXTRACTION_MODE
MODEL_SELECTION
FIELD_SCHEMA
CONFIDENCE_THRESHOLDS
HUMAN_REVIEW_POLICY
OUTPUT_CONTRACT
SECURITY_MODEL
SPECIAL_CASES
VALIDATION_PLAN
```

For example, if the user needs invoice extraction with line items, confidence thresholds, human review, and a normalized JSON handoff, the agent configures the extraction baseline rather than a search or RAG pipeline.

## Document-to-Search Pipeline Reconfiguration

Document-to-search pipeline reconfiguration is for scenarios where extracted documents need to become searchable, cited, filterable, vectorized, or RAG-ready in Azure AI Search.

The Document-to-Search Pipeline Reconfigurable Agent adapts these points:

```text
DOCUMENT_INTELLIGENCE_ENDPOINT
DOCUMENT_INTELLIGENCE_MODEL_ID
DOCUMENT_SOURCES
EXTRACTION_PIPELINE
NORMALIZED_DOCUMENT_SCHEMA
METADATA_ENRICHMENT
CHUNKING_POLICY
SEARCH_ENDPOINT
SEARCH_INDEX
SEARCH_INDEX_SCHEMA
VECTORIZATION_POLICY
CITATION_POLICY
INGESTION_MODE
SECURITY_MODEL
SPECIAL_CASES
VALIDATION_PLAN
```

For example, if the user needs contracts extracted, chunked by sections, enriched with metadata, indexed into Azure AI Search, and returned with page citations for RAG, the agent configures the extraction-to-indexing pipeline and hands off to Classic Search, RAG Search, or Agentic Retrieval as needed.

## Multimodal Knowledge Pipeline Reconfiguration

Multimodal knowledge pipeline reconfiguration is for mixed content where PDFs, scans, images, screenshots, charts, diagrams, tables, and visual assets need OCR, visual metadata, enrichment, indexing, citations, or RAG readiness.

The Multimodal Knowledge Pipeline Reconfigurable Agent adapts these points:

```text
CONTENT_SOURCES
CONTENT_TYPES
VISION_ANALYSIS_MODE
DOCUMENT_INTELLIGENCE_MODE
NORMALIZED_CONTENT_SCHEMA
METADATA_ENRICHMENT
CHUNKING_POLICY
SEARCH_ENDPOINT
SEARCH_INDEX
SEARCH_INDEX_SCHEMA
VECTORIZATION_POLICY
CITATION_POLICY
INGESTION_MODE
SECURITY_MODEL
SPECIAL_CASES
VALIDATION_PLAN
```

For example, if the user needs a knowledge base over scanned PDFs, screenshots, and diagrams with page and region citations, the agent configures OCR, visual metadata, normalization, chunking, indexing, and search/RAG handoffs.

## Speech And Conversation Intelligence Reconfiguration

Speech and conversation intelligence reconfiguration is for audio-first workflows where recordings or conversations need transcription, diarization, translation, summarization, searchable transcripts, QA, privacy controls, or analytics.

The Speech & Conversation Intelligence Reconfigurable Agent adapts these points:

```text
AUDIO_SOURCES
AUDIO_FORMATS
LANGUAGE_POLICY
TRANSCRIPTION_MODE
SPEAKER_DIARIZATION
TRANSCRIPT_SCHEMA
ENRICHMENT_POLICY
PRIVACY_POLICY
SEARCH_ENDPOINT
SEARCH_INDEX
SEARCH_INDEX_SCHEMA
RAG_OR_QA_POLICY
INGESTION_MODE
SECURITY_MODEL
SPECIAL_CASES
VALIDATION_PLAN
```

For example, if the user needs support-call transcripts with speaker turns, summaries, sentiment, PII redaction, and searchable citations by timestamp, the agent configures the speech-to-transcript-to-search baseline.

## Responsible AI Guardrail Reconfiguration

Responsible AI guardrail reconfiguration is for reusable safety and governance controls around Azure AI workflows, including chat, RAG, agentic retrieval, document extraction, multimodal enrichment, speech analytics, and generated media.

The Responsible AI Guardrail Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
INPUT_CHANNELS
OUTPUT_CHANNELS
RISK_PROFILE
CONTENT_SAFETY_POLICY
PROMPT_INJECTION_POLICY
GROUNDING_POLICY
PII_AND_PRIVACY_POLICY
PROTECTED_CONTENT_POLICY
HUMAN_ESCALATION_POLICY
ABUSE_MONITORING_POLICY
VALIDATION_PLAN
```

For example, if the user needs an enterprise RAG app to resist indirect prompt injection, require citations, redact PII, escalate risky answers, and monitor blocked prompts, the agent configures a layered guardrail baseline.

## AI Evaluation And Quality Reconfiguration

AI evaluation and quality reconfiguration is for reusable quality gates around Azure AI workflows, including datasets, metrics, thresholds, groundedness, citation accuracy, safety checks, regression testing, release gates, and validation evidence.

The AI Evaluation & Quality Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
EVALUATION_OBJECTIVES
DATASET_POLICY
METRIC_SET
THRESHOLDS_AND_GATES
GROUNDING_AND_CITATION_CHECKS
SAFETY_EVALUATION_POLICY
REGRESSION_PLAN
EVIDENCE_PACKAGE
VALIDATION_PLAN
```

For example, if the user needs a RAG app release gate with groundedness scores, citation accuracy checks, regression replay, safety evaluation, and reviewer signoff, the agent configures a measurable quality baseline instead of a broad test checklist.

## Tool-Using Workflow Reconfiguration

Tool-using workflow reconfiguration is for AI workflows that call APIs, Azure Functions, business systems, queues, MCP tools, or actions and need clear contracts, authorization, retries, idempotency, approvals, audit logs, and error handling.

The Tool-Using Workflow Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
TOOL_INVENTORY
TOOL_CONTRACTS
AUTHORIZATION_MODEL
SIDE_EFFECT_POLICY
RETRY_AND_IDEMPOTENCY_POLICY
APPROVAL_AND_ESCALATION_POLICY
AUDIT_AND_TRACE_POLICY
ERROR_HANDLING_POLICY
VALIDATION_PLAN
```

For example, if the user needs an assistant that can create support tickets, call inventory APIs, and request refunds with approval and audit evidence, the agent configures the tool-use baseline around explicit side-effect controls.

## Human Review And Escalation Reconfiguration

Human review and escalation reconfiguration is for human-in-the-loop workflows around uncertain, risky, low-confidence, policy-sensitive, or high-impact AI outputs.

The Human Review & Escalation Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
REVIEW_TRIGGERS
CONFIDENCE_POLICY
REVIEW_QUEUE
REVIEWER_ROLES
EVIDENCE_PACKAGE
OVERRIDE_POLICY
FEEDBACK_CAPTURE
AUDIT_AND_RETENTION_POLICY
VALIDATION_PLAN
```

For example, if the user needs low-confidence document extractions and policy-sensitive generated answers routed to reviewers with an evidence package, SLA, override reason, and feedback capture, the agent configures a human review control path.

## Knowledge Freshness And Reindexing Reconfiguration

Knowledge freshness and reindexing reconfiguration is for keeping Azure AI Search, RAG, agentic retrieval, document-to-search, multimodal, and transcript knowledge workflows current after the first index is built.

The Knowledge Freshness & Reindexing Reconfigurable Agent adapts these points:

```text
KNOWLEDGE_WORKFLOW
SOURCE_INVENTORY
FRESHNESS_REQUIREMENTS
CHANGE_DETECTION_POLICY
DELETION_POLICY
REINDEXING_POLICY
REPROCESSING_TRIGGERS
CITATION_FRESHNESS_POLICY
MONITORING_AND_ALERTS
VALIDATION_PLAN
```

For example, if the user needs a RAG corpus to pick up changed files hourly, remove deleted documents, refresh embeddings after chunking changes, and warn on stale citations, the agent configures the freshness and reindexing baseline.

## Observability And Continuous Improvement Reconfiguration

Observability and continuous improvement reconfiguration is for production AI applications that need traces, quality telemetry, user feedback, failed-answer review, drift detection, dashboards, alerts, continuous evaluation, and improvement backlog handoffs.

The Observability & Continuous Improvement Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
OBSERVABILITY_OBJECTIVES
TRACE_POLICY
QUALITY_SIGNAL_POLICY
FEEDBACK_CAPTURE
DRIFT_DETECTION_POLICY
DASHBOARD_AND_ALERTS
CONTINUOUS_EVALUATION_POLICY
IMPROVEMENT_BACKLOG
VALIDATION_PLAN
```

For example, if the user needs a support assistant to capture retrieval traces, track no-answer rates, review failed answers, detect index drift, and feed fixes into a monthly prompt/index improvement cycle, the agent configures the improvement loop.

## Cost And Capacity Governance Reconfiguration

Cost and capacity governance reconfiguration is for Azure AI applications that need model cost controls, Azure AI Search capacity planning, embedding cost policy, batch versus realtime tradeoffs, quotas, rate limits, caching, retention, budgets, and alerts.

The Cost & Capacity Governance Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
USAGE_PROFILE
MODEL_COST_POLICY
SEARCH_CAPACITY_POLICY
EMBEDDING_AND_INDEXING_COST_POLICY
BATCH_REALTIME_POLICY
QUOTA_AND_RATE_LIMIT_POLICY
CACHE_AND_RETENTION_POLICY
BUDGET_AND_ALERT_POLICY
VALIDATION_PLAN
```

For example, if the user needs to control RAG costs across model calls, embeddings, semantic ranking, evaluation runs, traces, and peak query traffic, the agent configures cost and capacity policies with explicit quality and latency tradeoffs.

## What The Agents Produce

Reconfigurable agents are requirements-driven. They do not invent Azure resources or silently assume endpoints, indexes, models, or knowledge sources. They produce a plan with:

- baseline configuration
- user-specific changes
- missing inputs
- special-case handling
- validation checks
- handoffs to auth, security, monitoring, operations, or implementation agents

The overall flow is:

```text
User requirements
  -> choose a reconfigurable category
  -> choose Search / Document Extraction / Document-to-Search / Multimodal / Speech / Guardrail baseline
  -> fill reconfiguration points
  -> identify gaps and validations
  -> hand off to planning or implementation
```

## Important Boundary

These are prebuilt configurable design agents, not runtime agents that mutate their own code. Their configuration is the structured contract and decision profile they generate for a user's specific scenario.
