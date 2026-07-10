# Azure AI Agent Foundry Catalog

## Discovery

Start with **Azure AI Agent Foundry Orchestrator** for broad requests. It routes to learning, application, capability, or shared platform agents.

For reusable Azure AI Search starting points, use **Azure AI Search Reconfigurable Orchestrator**. It routes users to prebuilt reconfigurable agents for classic search, RAG search, or agentic retrieval based on their requirements.

For reusable document processing starting points, use **Document Intelligence Reconfigurable Agent** for extraction-only scenarios and **Document-to-Search Pipeline Reconfigurable Agent** when extracted documents must become searchable, cited, or RAG-ready.

## Learning Orchestrators

| Area | Agent | Source Coverage |
| --- | --- | --- |
| Azure AI Services foundations | Azure AI Services Foundation Orchestrator | provisioning, security, monitoring, containers, content safety |
| Vision solutions | Vision Solutions Orchestrator | image analysis, image classification, object detection, face, OCR, video, generative vision |
| NLP solutions | NLP Solutions Orchestrator | text analytics, translation, speech, conversational language, Q&A, bot scenarios |
| Knowledge mining and search | Knowledge Mining Search Orchestrator, Azure AI Search Training Agent | Azure AI Search, classic search, agentic retrieval, custom skills, knowledge stores, indexing, vector/hybrid/multimodal search |
| Document intelligence | Document Intelligence Orchestrator, Document Intelligence Training Agent | quickstarts, Studio, prebuilt/custom extraction, custom classification, composed models, confidence scores, search pipeline integration |
| Generative AI | Generative AI Solutions Orchestrator | Azure OpenAI, chat, embeddings, RAG, prompt patterns, Foundry integration |

## Application Agent Blueprints

Use **Application Planning Companion Agent** after the design is selected. It tags along with the application steps, manages decisions and tasks, and coordinates handoffs without terminal execution. Use **Application Implementation Validation Agent** when a bounded step needs file changes, terminal commands, tests, local servers, or validation evidence.

## Azure AI Search Prebuilt Reconfigurable Agents

Use this category when users want configurable baseline agents with common Azure AI Search capabilities, common use cases, and explicit reconfiguration points for special cases.

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| Azure AI Search Reconfigurable Orchestrator | Choose between classic search, RAG search, and agentic retrieval configurable baselines | route decision, common reconfiguration profile, pattern-specific gaps, handoffs |
| Classic Search Reconfigurable Agent | Configure direct index-first search for user-specific data, query features, relevance, security, and validation | baseline configuration, reconfiguration points, index/query/relevance plan, validation checks |
| RAG Search Reconfigurable Agent | Configure Azure AI Search grounded RAG with retrieval, chunking, embeddings, citations, prompt assembly, and evaluation | baseline configuration, retrieval/chunking/prompt plan, grounding policy, evaluation checks |
| Agentic Retrieval Reconfigurable Agent | Configure Azure AI Search agentic retrieval with knowledge bases, knowledge sources, planning, references, activity logs, and synthesis | baseline configuration, knowledge source plan, reasoning/synthesis notes, reference/activity-log validation |

## Document Intelligence Prebuilt Reconfigurable Agents

Use this category when users want configurable baseline agents for structured document extraction or document-to-search pipelines with explicit reconfiguration points for special cases.

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| Document Intelligence Reconfigurable Agent | Configure document extraction for user-specific document types, models, field schemas, confidence thresholds, human review, output contracts, security, and validation | baseline configuration, model and schema plan, confidence/review policy, output contract, validation checks |
| Document-to-Search Pipeline Reconfigurable Agent | Configure Document Intelligence extraction into Azure AI Search with normalization, metadata enrichment, chunking, vectorization, citations, and RAG/search readiness | extraction-to-index plan, normalized schema, chunk/index/vector plan, citation policy, search/RAG handoffs, validation checks |

## Cross-Modal And Guardrail Prebuilt Reconfigurable Agents

Use this category when users need configurable baselines for mixed visual content, audio/conversation content, or reusable safety controls around Azure AI applications.

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| Multimodal Knowledge Pipeline Reconfigurable Agent | Configure pipelines for PDFs, scans, images, screenshots, diagrams, charts, visual assets, OCR, visual metadata, Azure AI Search indexing, citations, and RAG/search readiness | multimodal ingestion plan, OCR/vision analysis plan, normalized content schema, chunk/index/vector plan, citation policy, validation checks |
| Speech & Conversation Intelligence Reconfigurable Agent | Configure audio and conversation pipelines with speech-to-text, diarization, translation, transcript normalization, summarization, searchable transcript indexing, privacy, and validation | audio ingestion plan, transcription/diarization policy, transcript schema, enrichment/indexing plan, privacy policy, validation checks |
| Responsible AI Guardrail Reconfigurable Agent | Configure reusable safety controls for AI workflows, including content safety, prompt-injection defenses, groundedness, PII redaction, human escalation, protected-content handling, monitoring, and validation | risk profile, guardrail policy, grounding/privacy/escalation plan, safety test plan, monitoring handoffs |

## Quality, Workflow, And Human Review Prebuilt Reconfigurable Agents

Use this category when users need configurable baselines for AI quality gates, tool/action workflows, or human review and escalation loops around Azure AI applications.

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| AI Evaluation & Quality Reconfigurable Agent | Configure reusable evaluation datasets, metrics, thresholds, groundedness checks, citation accuracy, regression tests, release gates, and validation evidence | evaluation configuration, dataset and metric plan, thresholds and gates, evidence package, monitoring handoffs |
| Tool-Using Workflow Reconfigurable Agent | Configure AI workflows that call APIs, functions, business systems, queues, MCP tools, or actions with auth, retries, idempotency, approvals, audit logs, and validation | tool inventory, tool contracts, auth and side-effect policy, retry/idempotency plan, approval/audit policy, validation checks |
| Human Review & Escalation Reconfigurable Agent | Configure human-in-the-loop review, confidence thresholds, review queues, reviewer roles, escalation paths, override policy, feedback capture, audit evidence, SLAs, and validation | review trigger policy, queue and role plan, evidence package, override and feedback policy, audit/SLA checks |

## Lifecycle And Governance Prebuilt Reconfigurable Agents

Use this category when users need configurable baselines for running Azure AI applications over time: keeping knowledge fresh, measuring and improving behavior, governing cost and capacity, securing boundaries, and connecting data sources.

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| Knowledge Freshness & Reindexing Reconfigurable Agent | Configure source freshness, incremental sync, deletion handling, reprocessing triggers, stale-content detection, citation freshness, reindexing, monitoring, and validation for search/RAG/agentic knowledge workflows | source inventory, change/deletion policy, reindex/reprocessing plan, citation freshness checks, monitoring and validation handoffs |
| Observability & Continuous Improvement Reconfigurable Agent | Configure traces, quality telemetry, user feedback, failed-answer review, drift detection, dashboards, alerts, continuous evaluation, and improvement backlog handoffs | trace and signal plan, feedback loop, drift policy, dashboard/alert policy, continuous evaluation plan, improvement backlog |
| Cost & Capacity Governance Reconfigurable Agent | Configure model and Search capacity, embedding cost policy, batch versus realtime tradeoffs, quotas, rate limits, caching, retention, budgets, alerts, and validation | usage profile, model/Search/embedding policy, quota and cache controls, budget/alert policy, validation checks |
| Security, RBAC & Network Boundary Reconfigurable Agent | Configure identity, RBAC, least privilege, private endpoints, firewalls, egress, secrets, data-access boundaries, audit, compliance, and validation for Azure AI workflows | identity and RBAC policy, private networking and firewall plan, secret/data-access boundaries, audit and validation checks |
| Data Ingestion & Source Connector Reconfigurable Agent | Configure Blob, SharePoint, OneLake, SQL, API, queue, file-drop, transcript, and mixed source ingestion with auth, metadata mapping, change/deletion handling, retries, dead letters, and validation | source inventory, connector and auth policy, schema/metadata mapping, retry/dead-letter plan, downstream handoffs, validation checks |

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| Application Planning Companion Agent | Track and manage implementation steps after an app design is chosen | implementation tracker, task ownership, handoff prompts, validation plan |
| Application Implementation Validation Agent | Implement bounded steps and run validation commands | files changed, commands run, validation result, remaining issues |
| Vision Chat App Agent | Build image-aware chat, visual Q&A, inspection, retail assistant, support assistant | config contract, integration plan, prompt/image input pattern |
| Image Generation App Agent | Add text-to-image generation to an app | model config, moderation notes, output storage contract |
| Video Generation App Agent | Generate, poll, remix, and download videos | async workflow, polling policy, download/remix contract |
| Content Understanding Metadata Agent | Extract image metadata for search or asset management | analyzer schema, output JSON shape, integration guidance |
| Classic Search App Agent | Build direct index-first Azure AI Search applications | index schema, ingestion plan, query/relevance plan, validation checks |
| RAG Search App Agent | Build retrieval, hybrid/vector search, and knowledge mining flows | index strategy, retrieval contract, grounding flow |
| Agentic Retrieval App Agent | Build Azure AI Search agentic retrieval applications with knowledge bases and knowledge sources | knowledge base/source plan, indexed-vs-remote decision, references, activity log validation |
| Document Processing App Agent | Extract structured data from documents and forms | extraction pipeline, model choice, confidence/validation strategy |
| Document Extraction App Agent | Build preconfigured Document Intelligence extraction apps for invoices, receipts, forms, IDs, custom fields, classifiers, or composed models | model selection, extraction schema, confidence review, validation plan |
| Document Knowledge Pipeline Agent | Send Document Intelligence output into Azure AI Search, knowledge mining, RAG, metadata enrichment, or custom skill pipelines | normalized document schema, index/RAG contract, citation policy, reprocessing plan |

## Application Design Specialists

Use these specialists when a new application is still being shaped and needs design decisions before blueprint configuration or implementation.

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| Architecture & Design Agent | Turn a new app idea into components, boundaries, request flows, data flows, and design decisions | architecture summary, component responsibilities, flow, risks, handoffs |
| API & Integration Contract Agent | Define API, CLI, event, webhook, tool, or service integration contracts | schemas, error contract, retry behavior, integration assumptions, mocks |
| Data & Storage Design Agent | Design persistence, indexing, metadata, generated asset, retention, and audit patterns | entity and asset model, storage/indexing recommendations, lifecycle notes |
| Configuration & Environment Contract Agent | Define settings, `.env`, environment variables, feature flags, endpoint placeholders, and validation rules | configuration contract, environment matrix, secret handling, preflight checks |
| Test & Evaluation Strategy Agent | Plan build-time tests, mocks, manual validation, AI quality evaluations, datasets, and acceptance criteria | validation layers, evaluation plan, test data, mocks, acceptance criteria |
| UX & Human Workflow Agent | Design user journeys, review queues, confidence thresholds, fallback states, feedback capture, and human-in-the-loop flows | user journeys, review workflow, fallback states, feedback loop, UX handoff |

## Shared Platform Agents

| Agent | Use When |
| --- | --- |
| Foundry Integration Agent | Connect apps to Foundry projects, models, deployments, and endpoints |
| Auth Config Agent | Configure Entra ID, `.env`, local auth, and endpoint validation |
| Responsible AI Safety Agent | Add safety, moderation, policy, and responsible AI checks |
| Security & Compliance Agent | Review security posture, threat models, data protection, RBAC, secrets, and compliance readiness |
| Operations Readiness Agent | Prepare production readiness, runbooks, rollback, support handoff, incident response, quotas, and cost guardrails |
| Monitoring & Evaluation Agent | Define telemetry, tracing, Azure Monitor/Application Insights signals, alerting, evaluation checks, and quality monitoring |
