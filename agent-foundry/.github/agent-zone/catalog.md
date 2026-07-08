# Azure AI Agent Foundry Catalog

## Discovery

Start with **Azure AI Agent Foundry Orchestrator** for broad requests. It routes to learning, application, capability, or shared platform agents.

## Learning Orchestrators

| Area | Agent | Source Coverage |
| --- | --- | --- |
| Azure AI Services foundations | Azure AI Services Foundation Orchestrator | provisioning, security, monitoring, containers, content safety |
| Vision solutions | Vision Solutions Orchestrator | image analysis, image classification, object detection, face, OCR, video, generative vision |
| NLP solutions | NLP Solutions Orchestrator | text analytics, translation, speech, conversational language, Q&A, bot scenarios |
| Knowledge mining and search | Knowledge Mining Search Orchestrator | Azure AI Search, custom skills, knowledge stores, indexing |
| Document intelligence | Document Intelligence Orchestrator | prebuilt/custom extraction, composed models, search pipeline integration |
| Generative AI | Generative AI Solutions Orchestrator | Azure OpenAI, chat, embeddings, RAG, prompt patterns, Foundry integration |

## Application Agent Blueprints

Use **Application Planning Companion Agent** after the design is selected. It tags along with the application steps, manages decisions and tasks, and coordinates handoffs without terminal execution. Use **Application Implementation Validation Agent** when a bounded step needs file changes, terminal commands, tests, local servers, or validation evidence.

| Agent | Use When | Primary Outputs |
| --- | --- | --- |
| Application Planning Companion Agent | Track and manage implementation steps after an app design is chosen | implementation tracker, task ownership, handoff prompts, validation plan |
| Application Implementation Validation Agent | Implement bounded steps and run validation commands | files changed, commands run, validation result, remaining issues |
| Vision Chat App Agent | Build image-aware chat, visual Q&A, inspection, retail assistant, support assistant | config contract, integration plan, prompt/image input pattern |
| Image Generation App Agent | Add text-to-image generation to an app | model config, moderation notes, output storage contract |
| Video Generation App Agent | Generate, poll, remix, and download videos | async workflow, polling policy, download/remix contract |
| Content Understanding Metadata Agent | Extract image metadata for search or asset management | analyzer schema, output JSON shape, integration guidance |
| RAG Search App Agent | Build retrieval, hybrid/vector search, and knowledge mining flows | index strategy, retrieval contract, grounding flow |
| Document Processing App Agent | Extract structured data from documents and forms | extraction pipeline, model choice, confidence/validation strategy |

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
| Azure Knowledge Access Architect | Plan secure Azure Storage, Azure AI Search, Foundry IQ, and Foundry agent knowledge access; choose classic/vector/hybrid/multimodal/agentic retrieval; guide RBAC, firewall, private endpoint, DNS, and reuse-versus-create decisions |
| Auth Config Agent | Configure Entra ID, `.env`, local auth, and endpoint validation |
| Responsible AI Safety Agent | Add safety, moderation, policy, and responsible AI checks |
| Security & Compliance Agent | Review security posture, threat models, data protection, RBAC, secrets, and compliance readiness |
| Operations Readiness Agent | Prepare production readiness, runbooks, rollback, support handoff, incident response, quotas, and cost guardrails |
| Monitoring & Evaluation Agent | Define telemetry, tracing, Azure Monitor/Application Insights signals, alerting, evaluation checks, and quality monitoring |
