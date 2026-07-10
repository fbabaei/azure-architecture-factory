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

The lifecycle and governance prebuilt reconfigurable category adds five specialized configurable agents:

- Knowledge Freshness & Reindexing Reconfigurable Agent
- Observability & Continuous Improvement Reconfigurable Agent
- Cost & Capacity Governance Reconfigurable Agent
- Security, RBAC & Network Boundary Reconfigurable Agent
- Data Ingestion & Source Connector Reconfigurable Agent

For a step-by-step user manual with starter prompts, examples, handoffs, and validation checks, see [Reconfigurable Agents Quick Start](reconfigurable-agents-quick-start.md). For an end-to-end mock project example, see [Reconfigurable Agents Walkthrough](reconfigurable-agents-walkthrough.md).

## How Reconfiguration Works

1. The user starts with Azure AI Search Reconfigurable Orchestrator.
2. The orchestrator decides whether the request is classic search, RAG search, agentic retrieval, mixed, evaluation/quality, tool workflow, human review, freshness/reindexing, observability/improvement, cost/capacity, security/RBAC/network boundaries, ingestion/source connectors, or missing enough detail.
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

## Coordinating Multiple Agents

A real architecture usually needs more than one reconfigurable agent — for example a document-to-search pipeline plus a RAG agent plus a security/RBAC agent plus an observability agent. These agents do not run in parallel on a server. They are coordinated as an approval-gated, sequential handoff workflow that you drive in VS Code / Copilot.

Here is how a single portal run handles that:

1. **The orchestrator always leads as lead architect.** Every run starts with an orchestrator (the Azure AI Application Orchestrator for app scenarios, or the Azure AI Learning Orchestrator for learning plans) as the first owner agent. It decomposes the submission into capabilities, maps each to a single owner agent, owns cross-cutting concerns (security, cost, observability, responsible AI, freshness), sequences the handoffs, and records the key architecture decisions — before any specialist configuration begins. This holds whether you leave the agent field on **Route automatically** or explicitly pick a specialist.
2. **A specialist is chosen as the configuration owner.** If you pick an agent, it becomes the configuration owner in its own step under the lead architect. If you leave **Route automatically**, the portal scores every agent against your source text, input type, and reconfiguration profile and selects the best-fitting one (falling back to the Azure AI Search Reconfigurable Orchestrator if nothing matches strongly).
3. **The plan is built as a team.** Around the lead architect and specialist, the portal assembles a fixed supporting team of owner agents — planning companion, configuration/environment contract, security & compliance, test & evaluation, and implementation validation — plus an Architecture Design Agent when the input is a diagram.
4. **Execution mode is `approval-gated-handoff`.** The plan is an ordered set of steps, each with its own owner agent, starting with the lead architect's decomposition. Nothing runs until you approve.
5. **Agents hand off to each other.** Each reconfigurable agent's `Handoffs` section names the specialists it defers to (for example, an ingestion agent hands off to freshness, security, and document-to-search agents). Multi-agent composition happens through these handoffs, one approved step at a time.

Two practical patterns for a multi-capability architecture:

- **Orchestrator-first:** submit the whole architecture and let an orchestrator identify the needed capabilities and sequence the handoffs. The recommendation panel scores all agents, so secondary capabilities are visible in the reasons even though only the top agent is selected.
- **One capability per run:** run the runner multiple times, one reconfigurable agent per capability, and let the planning companion and configuration-contract agents keep the contracts consistent across runs.

> Note: `.agent.md` files are VS Code / Copilot customization files, not a hosted multi-agent runtime. "Multiple agents working together" means a coordinated, human-approved handoff workflow in the editor — not agents executing live in parallel on a server.

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

Observability and continuous improvement reconfiguration is for tracing, quality telemetry, feedback, drift detection, and a closed improvement loop over production AI workflows.

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

For example, if the user needs traces across a RAG pipeline, quality telemetry on citations, failed-answer review, drift alerts, and a continuous-evaluation loop feeding an improvement backlog, the agent configures the observability baseline.

## Cost And Capacity Governance Reconfiguration

Cost and capacity governance reconfiguration is for model and Azure AI Search cost/capacity controls across AI workloads.

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

For example, if the user needs token budgets per feature, Search SKU sizing, embedding cost controls, batch-versus-realtime tradeoffs, and budget alerts, the agent configures the cost and capacity baseline.

## Security, RBAC And Network Boundary Reconfiguration

Security, RBAC, and network boundary reconfiguration is for identity, least privilege, network isolation, and data-access boundaries across AI workflows.

The Security, RBAC & Network Boundary Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
SECURITY_SCOPE
IDENTITY_MODEL
RBAC_POLICY
NETWORK_BOUNDARY
PRIVATE_ENDPOINT_POLICY
FIREWALL_AND_EGRESS_POLICY
SECRET_AND_CONFIGURATION_POLICY
DATA_ACCESS_BOUNDARIES
AUDIT_AND_COMPLIANCE_POLICY
VALIDATION_PLAN
```

For example, if the user needs managed identity, least-privilege RBAC, private endpoints, firewall/egress rules, and document-level data-access boundaries, the agent configures the security baseline.

## Data Ingestion And Source Connector Reconfiguration

Data ingestion and source connector reconfiguration is for connecting sources and feeding normalized content into AI and search workflows.

The Data Ingestion & Source Connector Reconfigurable Agent adapts these points:

```text
INGESTION_WORKFLOW
SOURCE_INVENTORY
CONNECTOR_TYPES
AUTH_AND_ACCESS_POLICY
INGESTION_MODE
SCHEMA_AND_METADATA_MAPPING
CHANGE_AND_DELETION_HANDLING
RETRY_AND_DEADLETTER_POLICY
NORMALIZATION_AND_HANDOFF
OBSERVABILITY_AND_AUDIT_POLICY
VALIDATION_PLAN
```

For example, if the user needs Blob and SharePoint connectors with incremental ingestion, metadata mapping, deletion handling, and dead-letter retries feeding a search index, the agent configures the ingestion baseline.

## Conversational Assistant Reconfiguration

Conversational assistant reconfiguration is for reusable multi-turn chat assistants over Azure OpenAI chat models.

The Conversational Assistant Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
CHANNELS
PERSONA_AND_SYSTEM_PROMPT
MODEL_DEPLOYMENT
CONVERSATION_MEMORY
CONTEXT_WINDOW_POLICY
TOOL_AND_GROUNDING_HOOKS
STREAMING_POLICY
SESSION_STATE_POLICY
SAFETY_AND_FALLBACK_POLICY
VALIDATION_PLAN
```

For example, if the user needs a support copilot with a defined persona, summarized history, RAG grounding hooks, streaming, and safe fallback, the agent configures the conversational baseline.

## Translation And Localization Reconfiguration

Translation and localization reconfiguration is for language coverage, detection, terminology, and localized experiences.

The Translation & Localization Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
SOURCE_AND_TARGET_LANGUAGES
LANGUAGE_DETECTION_POLICY
TRANSLATION_SERVICE
GLOSSARY_AND_TERMINOLOGY
CONTENT_TYPES
LOCALIZATION_POLICY
QUALITY_AND_REVIEW_POLICY
PRIVACY_POLICY
VALIDATION_PLAN
```

For example, if the user needs multilingual document translation with a brand glossary, do-not-translate terms, and human review on low-quality output, the agent configures the translation baseline.

## Vision Analysis Reconfiguration

Vision analysis reconfiguration is for image tagging, detection, classification, and OCR that is not primarily document field extraction.

The Vision Analysis Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
IMAGE_SOURCES
ANALYSIS_TASKS
VISION_SERVICE_OR_MODEL
OCR_POLICY
OUTPUT_SCHEMA
CONFIDENCE_THRESHOLDS
HUMAN_REVIEW_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs image tagging and OCR with confidence thresholds routing low-confidence results to reviewers, the agent configures the vision-analysis baseline.

## Embedding And Vectorization Reconfiguration

Embedding and vectorization reconfiguration is for embedding model, dimensions, chunk-to-vector mapping, and re-embedding lifecycle.

The Embedding & Vectorization Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
CONTENT_INVENTORY
EMBEDDING_MODEL
EMBEDDING_DIMENSIONS
CHUNK_TO_VECTOR_STRATEGY
VECTOR_INDEX_CONFIG
RE_EMBEDDING_POLICY
COST_AND_LATENCY_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs an embedding model and dimensions aligned to a target vector index with a re-embedding plan for content changes, the agent configures the vectorization baseline.

## Model Routing And AI Gateway Reconfiguration

Model routing and AI gateway reconfiguration is for routing across multiple models/regions with limits, fallback, and caching.

The Model Routing & AI Gateway Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
MODEL_INVENTORY
ROUTING_POLICY
LOAD_BALANCING_POLICY
TOKEN_LIMIT_POLICY
FALLBACK_POLICY
SEMANTIC_CACHE_POLICY
OBSERVABILITY_AND_METRICS
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs multiple model deployments behind one endpoint with load balancing, token limits, fallback, and semantic caching, the agent configures the gateway baseline.

## Fine-Tuning And Model Customization Reconfiguration

Fine-tuning and model customization reconfiguration is for customizing models with SFT, DPO, RFT, or distillation when prompting and retrieval are insufficient.

The Fine-Tuning & Model Customization Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
BASE_MODEL
CUSTOMIZATION_METHOD
TRAINING_DATA_POLICY
GRADER_OR_REWARD_POLICY
HYPERPARAMETERS
EVALUATION_AND_ACCEPTANCE
DEPLOYMENT_POLICY
COST_AND_QUOTA_POLICY
VALIDATION_PLAN
```

For example, if the user needs task specialization with a curated dataset, a grader, and an evaluation gate against a baseline before deployment, the agent configures the customization baseline.

## Image Generation Reconfiguration

Image generation reconfiguration is for text-to-image generation with prompt templates, moderation, and asset handling.

The Image Generation Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
IMAGE_MODEL
PROMPT_TEMPLATES
SIZE_AND_QUALITY
MODERATION_POLICY
OUTPUT_AND_STORAGE
RATE_AND_COST_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs branded marketing images with prompt templates, moderation, and stored assets, the agent configures the image-generation baseline.

## Video Generation Reconfiguration

Video generation reconfiguration is for text-to-video and image-to-video generation with async job handling and moderation.

The Video Generation Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
VIDEO_MODEL
GENERATION_MODE
PROMPT_AND_INPUT_ASSETS
DURATION_AND_RESOLUTION
ASYNC_JOB_POLICY
MODERATION_POLICY
OUTPUT_AND_STORAGE
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs short promotional clips generated asynchronously with polling, moderation, and stored MP4 output, the agent configures the video-generation baseline.

## Knowledge Graph And GraphRAG Reconfiguration

Knowledge graph and GraphRAG reconfiguration is for entity/relationship extraction and graph-augmented retrieval over a corpus.

The Knowledge Graph & GraphRAG Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
SOURCE_CORPUS
ENTITY_AND_RELATIONSHIP_SCHEMA
EXTRACTION_METHOD
GRAPH_STORE
GRAPH_INDEXING_POLICY
GRAPHRAG_RETRIEVAL_POLICY
GROUNDING_AND_CITATION_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs multi-hop questions answered by combining graph traversal with text retrieval and citations, the agent configures the GraphRAG baseline.

## Batch And Bulk Inference Reconfiguration

Batch and bulk inference reconfiguration is for large-scale offline processing where latency is not critical.

The Batch & Bulk Inference Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
WORKLOAD_PROFILE
BATCH_JOB_DESIGN
INPUT_AND_OUTPUT_FORMAT
CHECKPOINT_AND_RESUME
THROUGHPUT_AND_QUOTA
ERROR_AND_RETRY_POLICY
COST_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs to classify millions of records offline with checkpointing, result reconciliation, and cost-optimized batching, the agent configures the batch baseline.

## Agent Memory And State Reconfiguration

Agent memory and state reconfiguration is for durable and cross-session memory beyond in-session history.

The Agent Memory & State Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
MEMORY_SCOPES
SHORT_TERM_MEMORY
LONG_TERM_MEMORY_STORE
SUMMARIZATION_POLICY
RETRIEVAL_POLICY
RETENTION_AND_PRIVACY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs per-user long-term memory with summarization, relevance-based recall, retention windows, and deletion, the agent configures the memory baseline.

## Content Generation And Summarization Reconfiguration

Content generation and summarization reconfiguration is for text summarization, drafting, and templated generation.

The Content Generation & Summarization Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
INPUT_CONTENT
GENERATION_TASKS
MODEL_DEPLOYMENT
PROMPT_AND_TEMPLATE_POLICY
OUTPUT_SCHEMA
STYLE_AND_TONE
GROUNDING_AND_FACTUALITY
SAFETY_POLICY
VALIDATION_PLAN
```

For example, if the user needs templated summaries with a defined tone, structured output, and factuality controls, the agent configures the generation baseline.

## Multi-Agent Orchestration Reconfiguration

Multi-agent orchestration reconfiguration is for coordinating multiple specialized agents toward a goal.

The Multi-Agent Orchestration Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
AGENT_INVENTORY
ORCHESTRATION_PATTERN
HANDOFF_CONTRACTS
PLANNING_POLICY
SHARED_STATE_AND_MEMORY
ERROR_AND_FALLBACK_POLICY
OBSERVABILITY_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs a planner/worker pattern with explicit handoff contracts, shared state, and cross-agent tracing, the agent configures the orchestration baseline.

## Data Privacy And PII Redaction Reconfiguration

Data privacy and PII redaction reconfiguration is for detecting and handling PII across prompts, documents, logs, and outputs.

The Data Privacy & PII Redaction Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
DATA_INVENTORY
PII_CATEGORIES
DETECTION_METHOD
REDACTION_OR_DEIDENTIFICATION_POLICY
DATA_RESIDENCY_POLICY
RETENTION_AND_MINIMIZATION
AUDIT_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs PII detected and redacted from inputs and logs with residency constraints and audit evidence, the agent configures the privacy baseline.

## Deployment And Release Reconfiguration

Deployment and release reconfiguration is for release strategy, promotion, versioning, and rollback of models and agent apps.

The Deployment & Release Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
DEPLOYMENT_TARGETS
RELEASE_STRATEGY
ENVIRONMENT_PROMOTION
VERSIONING_POLICY
ROLLBACK_POLICY
QUOTA_AND_CAPACITY
RELEASE_GATES
OBSERVABILITY_HOOKS
VALIDATION_PLAN
```

For example, if the user needs staged promotion with canary, versioning, rollback, and evaluation-based release gates, the agent configures the release baseline.

## Feedback And Continuous Learning Reconfiguration

Feedback and continuous learning reconfiguration is for capturing feedback and closing the loop into prompt optimization or fine-tuning.

The Feedback & Continuous Learning Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
FEEDBACK_SOURCES
FEEDBACK_SCHEMA
LABELING_AND_PREFERENCE_POLICY
DATASET_CURATION
LEARNING_LOOP_TARGET
GUARDRAILS_AND_REVIEW
PRIVACY_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs user ratings and corrections curated into a reviewed dataset that feeds prompt optimization, the agent configures the feedback-loop baseline.

## Recommendation And Personalization Reconfiguration

Recommendation and personalization reconfiguration is for ranking, personalization, and recommendations.

The Recommendation & Personalization Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
USER_AND_ITEM_DATA
PERSONALIZATION_SIGNALS
RECOMMENDATION_METHOD
RANKING_POLICY
COLD_START_POLICY
PRIVACY_AND_CONSENT
EVALUATION_METRICS
SECURITY_MODEL
VALIDATION_PLAN
```

For example, if the user needs personalized content recommendations with cold-start handling, diversity rules, consent controls, and evaluation metrics, the agent configures the recommendation baseline.

## Serverless And Event-Driven Hosting Reconfiguration

Serverless and event-driven hosting reconfiguration is about the *runtime* of an AI workload — where and how it actually runs — rather than what the AI does.

New to the catalog? Here is the distinction. Most reconfigurable agents decide *what* the AI does: search, RAG, document extraction, generation, guardrails. The Serverless & Event-Driven Hosting Reconfigurable Agent decides *where and how that work executes* on Azure: which compute service hosts it, what event starts it, how it scales, and how it stays reliable and affordable. Reach for it whenever a scenario mentions triggers, events, queues, schedules, scale-to-zero, cold starts, concurrency, or long-running background jobs.

What it decides, in plain terms:

- The hosting service — Azure Functions (event-driven code), Azure Container Apps (containerized services/APIs that can scale to zero), Container Apps Jobs (finite or scheduled batch runs), or Durable Functions (multi-step stateful orchestration).
- The trigger — HTTP request, timer/schedule, queue or topic message, event, or blob change that starts the workload.
- Scaling — scale-to-zero, minimum/maximum instances, and how many requests each instance handles at once.
- Reliability — retries, idempotency (safe re-processing of duplicate events), and dead-letter handling.
- The tradeoffs — cold-start vs. always-warm latency, state and durability, security (managed identity, public vs. private), and cost.

The Serverless & Event-Driven Hosting Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
WORKLOAD_SHAPE
HOSTING_TARGET
TRIGGERS_AND_BINDINGS
SCALE_POLICY
STATE_AND_DURABILITY
COLD_START_AND_LATENCY_POLICY
IDEMPOTENCY_AND_RETRY
SECURITY_MODEL
COST_POLICY
VALIDATION_PLAN
```

For example, if the user needs a RAG scoring step that runs on Azure Functions whenever a message lands on a queue, scales to zero when idle, and safely retries duplicate messages, the agent configures the serverless hosting baseline. It hands the AI logic back to the capability agents, the release process to Deployment & Release, the source connectors to Data Ingestion, and cost/security to the governance agents.



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

## Security, RBAC, And Network Boundary Reconfiguration

Security, RBAC, and network boundary reconfiguration is for Azure AI applications that need identity, least privilege, private networking, firewall and egress controls, secret handling, data-access boundaries, audit evidence, and compliance handoffs.

The Security, RBAC & Network Boundary Reconfigurable Agent adapts these points:

```text
AI_WORKFLOW
SECURITY_SCOPE
IDENTITY_MODEL
RBAC_POLICY
NETWORK_BOUNDARY
PRIVATE_ENDPOINT_POLICY
FIREWALL_AND_EGRESS_POLICY
SECRET_AND_CONFIGURATION_POLICY
DATA_ACCESS_BOUNDARIES
AUDIT_AND_COMPLIANCE_POLICY
VALIDATION_PLAN
```

For example, if the user needs an enterprise RAG app that uses managed identity, private Storage and Search access, document-level security, Key Vault references, denied-access tests, and audit evidence, the agent configures the boundary baseline and hands off to security, auth, and implementation specialists.

## Data Ingestion And Source Connector Reconfiguration

Data ingestion and source connector reconfiguration is for Azure AI applications that need reusable connector patterns before data reaches search, RAG, document processing, analytics, or agent workflows.

The Data Ingestion & Source Connector Reconfigurable Agent adapts these points:

```text
INGESTION_WORKFLOW
SOURCE_INVENTORY
CONNECTOR_TYPES
AUTH_AND_ACCESS_POLICY
INGESTION_MODE
SCHEMA_AND_METADATA_MAPPING
CHANGE_AND_DELETION_HANDLING
RETRY_AND_DEADLETTER_POLICY
NORMALIZATION_AND_HANDOFF
OBSERVABILITY_AND_AUDIT_POLICY
VALIDATION_PLAN
```

For example, if the user needs Blob, SharePoint, and SQL sources ingested into a RAG corpus with managed identity, metadata mapping, incremental updates, deletion handling, dead-letter replay, and downstream query validation, the agent configures the connector baseline and hands off to freshness, storage, search, and implementation specialists.

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
