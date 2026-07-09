# Azure AI Search Agents Step By Step

Use this guide when you want to learn Azure AI Search, choose the right Search-focused application agent, or start from a prebuilt reconfigurable Search agent.

Primary Microsoft Learn source: <https://learn.microsoft.com/azure/search/search-what-is-azure-search>.

## What Was Added

Azure AI Agent Foundry now includes three focused Azure AI Search agents:

| Agent | Use when |
| --- | --- |
| Azure AI Search Training Agent | You want a guided learning route through Azure AI Search concepts, quickstarts, classic search, vector/hybrid search, multimodal search, AI enrichment, agentic retrieval, security, pricing, and monitoring. |
| Classic Search App Agent | You want to design a direct index-first search application with indexes, indexers, data sources, skillsets, filters, facets, autocomplete, synonyms, semantic ranking, vector/hybrid search, and relevance tuning. |
| Agentic Retrieval App Agent | You want to design an app that uses Azure AI Search agentic retrieval with knowledge bases, knowledge sources, query planning, query decomposition, reasoning effort, references, activity logs, and optional answer synthesis. |

The existing Knowledge Mining Search Orchestrator remains the broad router. The existing RAG Search App Agent remains the right choice for conventional RAG patterns where the application owns prompt assembly, grounding behavior, citation checks, and generated answers over search results.

## Azure AI Search Prebuilt Reconfigurable Category

Use this category when you want a configurable baseline agent that covers common use cases but can be adapted for user-specific requirements and special cases.

| Agent | Use when |
| --- | --- |
| Azure AI Search Reconfigurable Orchestrator | You want help choosing between classic search, RAG search, and agentic retrieval before configuring a reusable baseline. |
| Classic Search Reconfigurable Agent | You want a configurable direct index-first search baseline with schema, ingestion, query features, relevance, security, and validation reconfiguration points. |
| RAG Search Reconfigurable Agent | You want a configurable RAG baseline over Azure AI Search with retrieval, chunking, embeddings, prompt assembly, citations, no-answer behavior, and evaluation. |
| Agentic Retrieval Reconfigurable Agent | You want a configurable agentic retrieval baseline with knowledge bases, knowledge sources, source mode, query planning, reasoning effort, synthesis, references, and activity logs. |

The reconfigurable agents are best when the user wants a reusable starting point. The existing Classic Search App Agent, RAG Search App Agent, and Agentic Retrieval App Agent remain useful when the user wants a narrower application blueprint.

For a deeper explanation of how these baselines adapt to user requirements, see [Reconfigurable Agents](reconfigurable-agents.md). For a new-user manual with concrete prompts and follow-up steps, see [Reconfigurable Agents Quick Start](reconfigurable-agents-quick-start.md). For a full mock project example, see [Reconfigurable Agents Walkthrough](reconfigurable-agents-walkthrough.md).

## How To Choose The Right Agent

Use Azure AI Search Training Agent when you are learning.

Use Classic Search App Agent when your app should send a query directly to a known search index and receive ranked search results.

Use RAG Search App Agent when your app retrieves chunks from Azure AI Search and then uses a model or agent to generate a grounded answer.

Use Agentic Retrieval App Agent when Azure AI Search should manage a knowledge base over one or more knowledge sources, plan/decompose the query, retrieve in parallel, rerank/merge results, and return references or synthesized answers for agent consumption.

Use Document Knowledge Pipeline Agent when Document Intelligence output must be normalized, chunked, enriched, and sent into Azure AI Search before retrieval.

## How To Use These Agents

Start with the agent name, then describe the scenario, data sources, user outcome, security constraints, and the decision you need. The agents are designed to split Azure AI Search work into the right lane early, so classic search, conventional RAG, and agentic retrieval do not get blended together.

Use Azure AI Search Training Agent when you are learning or deciding what Search capability fits.

```text
Azure AI Search Training Agent, help me understand classic search, RAG, and agentic retrieval. My scenario is an internal policy assistant over SharePoint and indexed PDFs.
```

Use Classic Search App Agent when the app should query Azure AI Search directly and return ranked results. This is for search boxes, filters, facets, autocomplete, synonyms, geo-search, semantic ranking, vector search, hybrid search, index schema design, ingestion, and relevance tuning.

```text
Classic Search App Agent, design a product catalog search app. I need keyword search, filters, facets, autocomplete, synonyms, semantic ranking, vector search, and secure access by product region.
```

Use Agentic Retrieval App Agent when Azure AI Search should act as the retrieval planner for an AI agent: knowledge bases, knowledge sources, query planning, query decomposition, parallel retrieval, semantic reranking, references, activity logs, reasoning effort, and optional answer synthesis.

```text
Agentic Retrieval App Agent, design an enterprise assistant using Azure AI Search agentic retrieval over SharePoint and indexed policy documents. I need permission-aware access, references, activity logs, no-answer behavior, and validation checks.
```

Use RAG Search App Agent when your application owns the RAG flow: retrieve chunks from Azure AI Search, assemble prompts, generate grounded answers, enforce citation/no-answer behavior, and evaluate answer quality.

```text
RAG Search App Agent, design a support assistant over indexed help articles. I need hybrid retrieval, chunking, citations, grounded answers, and unsupported-question behavior.
```

Use Knowledge Mining Search Orchestrator when you are not sure which Search-focused agent to choose.

```text
Knowledge Mining Search Orchestrator, route this scenario to the right agent: I have internal documents, users ask questions in chat, and I need citations plus permission-aware retrieval.
```

Use Azure AI Search Reconfigurable Orchestrator when you want the new prebuilt reconfigurable category.

```text
Azure AI Search Reconfigurable Orchestrator, help me choose and configure a reusable Search agent baseline. My app has product search, support articles, user-specific access, citations for generated answers, and special cases for region-based filtering.
```

## Beginner Flow

1. Start with Azure AI Search Training Agent.
2. Ask it to explain classic search vs. agentic retrieval.
3. Decide whether your scenario is search results, conventional RAG, or agentic retrieval.
4. If you want a reusable configurable baseline, move to Azure AI Search Reconfigurable Orchestrator.
5. If you want a narrow blueprint, move to Classic Search App Agent, RAG Search App Agent, or Agentic Retrieval App Agent.
6. Define the configuration contract.
7. Bring in Auth Config Agent for endpoint and identity details.
8. Bring in Security & Compliance Agent if access control, Private Link, document-level permissions, or compliance matters.
9. Bring in Monitoring & Evaluation Agent for retrieval quality, logs, metrics, alerts, and evaluation checks.
10. Use Application Planning Companion Agent to turn the design into implementation steps.
11. Use Application Implementation Validation Agent only when an approved step needs file edits, terminal commands, tests, local servers, or validation evidence.

## Learning Prompt

```text
Azure AI Search Training Agent, walk me through Azure AI Search from the Microsoft Learn introduction. Explain classic search, indexing, querying, vector search, hybrid search, multimodal search, AI enrichment, and agentic retrieval. Give me one checkpoint at a time and wait before continuing.
```

Expected output:

1. Learning goal.
2. Source references.
3. Step-by-step route.
4. Current checkpoint.
5. Classic search vs. agentic retrieval decision note.
6. Application follow-up agent.

## Classic Search App Prompt

```text
Classic Search App Agent, design a direct Azure AI Search experience for a product catalog. The app needs keyword search, filters, facets, autocomplete, relevance tuning, and secure access. Identify the index schema, ingestion method, query pattern, configuration contract, validation checks, and handoffs.
```

Expected output:

1. Search application route.
2. Index and ingestion plan.
3. Query and relevance plan.
4. Configuration contract.
5. Security and operations notes.
6. Validation checks.
7. Handoffs.

Use this agent when the app primarily returns search results, not generated answers.

## Reconfigurable Search Prompt

```text
Azure AI Search Reconfigurable Orchestrator, choose and configure a prebuilt Search agent baseline for my requirements. I need [search results / grounded answers / agentic retrieval], my data sources are [sources], my users need [experience], and my constraints are [security, freshness, latency, cost, compliance].
```

Expected output:

1. Recommended reconfigurable agent.
2. Route decision and why.
3. Common reconfiguration profile.
4. Pattern-specific configuration gaps.
5. Security, validation, cost, and operations checks.
6. Handoffs.

Use this route when you want a reusable baseline that can be adapted for special cases instead of a one-off application blueprint.

## Agentic Retrieval App Prompt

```text
Agentic Retrieval App Agent, design an Azure AI Search agentic retrieval app for an enterprise assistant over SharePoint and indexed policy documents. I need knowledge bases, knowledge sources, permission-aware access, references, activity logs, no-answer behavior, and evaluation checks.
```

Expected output:

1. Agentic retrieval fit decision.
2. Knowledge base and knowledge source plan.
3. Indexed vs. remote source decision.
4. Reasoning effort and answer synthesis notes.
5. Configuration contract.
6. Grounding, references, and activity log validation.
7. Security, cost, region, and operations checks.
8. Handoffs.

Use this agent when the search service should orchestrate retrieval for an agent instead of only returning direct index results.

## Conventional RAG Prompt

```text
RAG Search App Agent, design a RAG assistant over indexed support articles. I need hybrid retrieval, chunking, citations, no-answer behavior, and evaluation checks for grounded answers.
```

Expected output:

1. Index and retrieval plan.
2. Configuration contract.
3. Grounding and citation pattern.
4. Evaluation checks.
5. Failure behavior.
6. Handoffs.

Use this agent when your application or agent owns answer generation over retrieved search results.

## Configuration Cheat Sheet

Azure AI Search Reconfigurable Orchestrator asks for:

```text
USER_OUTCOME
DATA_SOURCES
SOURCE_FRESHNESS
RETRIEVAL_PATTERN
SECURITY_MODEL
GROUNDING_POLICY
VALIDATION_PLAN
```

Classic Search App Agent asks for:

```text
SEARCH_ENDPOINT
SEARCH_INDEX
DATA_SOURCES
INGESTION_MODE
INDEX_SCHEMA
QUERY_FEATURES
RELEVANCE_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

Agentic Retrieval App Agent asks for:

```text
SEARCH_ENDPOINT
KNOWLEDGE_BASE
KNOWLEDGE_SOURCES
SOURCE_MODE
RETRIEVAL_REASONING_EFFORT
QUERY_PLANNING_MODE
ANSWER_SYNTHESIS
GROUNDING_POLICY
SECURITY_MODEL
VALIDATION_PLAN
```

RAG Search App Agent asks for:

```text
SEARCH_ENDPOINT
SEARCH_INDEX
RETRIEVAL_MODE
EMBEDDING_DEPLOYMENT
GROUNDING_POLICY
```

## Important Guardrails

Do not invent search endpoints, index names, knowledge base names, knowledge source names, regions, model deployments, pricing, quotas, or feature support.

Treat preview features, Serverless tier constraints, region support, billing, and limits as things to verify before implementation.

Always validate retrieval quality. For generated answers, validate citations and unsupported-question behavior. For agentic retrieval, also validate references, activity logs, reasoning effort, latency, cost, and source coverage.

## Next Prompt

Start with:

```text
Azure AI Search Training Agent, help me decide whether my scenario should use classic search, RAG, or agentic retrieval. My scenario is: [describe your app].
```
