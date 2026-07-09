# Reconfigurable Agents

Reconfiguration means an agent is not a fixed one-scenario template. It is a reusable baseline that starts with common Azure AI Search patterns, then adapts its configuration contract to the user's requirements.

In this repo, the Azure AI Search prebuilt reconfigurable category uses one router and three specialized configurable agents:

- Azure AI Search Reconfigurable Orchestrator
- Classic Search Reconfigurable Agent
- RAG Search Reconfigurable Agent
- Agentic Retrieval Reconfigurable Agent

For a step-by-step user manual with starter prompts, examples, handoffs, and validation checks, see [Reconfigurable Agents Quick Start](reconfigurable-agents-quick-start.md). For an end-to-end mock project example, see [Reconfigurable Agents Walkthrough](reconfigurable-agents-walkthrough.md).

## How Reconfiguration Works

1. The user starts with Azure AI Search Reconfigurable Orchestrator.
2. The orchestrator decides whether the request is classic search, RAG search, agentic retrieval, mixed, or missing enough detail.
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
  -> Azure AI Search Reconfigurable Orchestrator
  -> choose Classic / RAG / Agentic Retrieval baseline
  -> fill reconfiguration points
  -> identify gaps and validations
  -> hand off to planning or implementation
```

## Important Boundary

These are prebuilt configurable design agents, not runtime agents that mutate their own code. Their configuration is the structured contract and decision profile they generate for a user's specific scenario.
