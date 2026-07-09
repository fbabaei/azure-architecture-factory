# Reconfigurable Agents Quick Start

Use this guide when you are new to the Azure AI Search prebuilt reconfigurable agents and want a practical path from a rough requirement to a usable configuration plan.

For an end-to-end mock project walkthrough, see [Reconfigurable Agents Walkthrough](reconfigurable-agents-walkthrough.md).

The reconfigurable agents help you choose and configure one of three Azure AI Search patterns:

- Classic search: direct index-first search results.
- RAG search: retrieval plus app-owned prompt assembly and grounded answer generation.
- Agentic retrieval: Azure AI Search-managed knowledge bases, knowledge sources, query planning, references, activity logs, and optional synthesis.

## Before You Start

Open this repo in VS Code and use VS Code Chat. The agents live under `.github/agents/` and should be available when this workspace is open.

You do not need Azure resource names to start. The agents can produce a requirements-driven plan with placeholders and missing-input notes. Do not provide secrets, API keys, or tokens in chat.

## 1. Start With The Router

Start with Azure AI Search Reconfigurable Orchestrator when you are not sure which search pattern fits.

Use this prompt shape:

```text
Azure AI Search Reconfigurable Orchestrator, help me choose and configure a reusable Search agent baseline.

My app: [describe the app]
Users need: [search results, grounded answers, agent assistant, or mixed]
Data sources: [documents, product catalog, SharePoint, Blob Storage, SQL, APIs, web, indexes]
Freshness needs: [live, near-real-time, scheduled, batch, archival]
Security constraints: [public, internal, role-based, tenant-specific, permission-aware, Private Link, compliance]
Grounding needs: [citations, references, activity logs, no-answer behavior]
Special cases: [regions, multilingual, regulated data, multiple tenants, high latency sensitivity]
```

Short example:

```text
Azure AI Search Reconfigurable Orchestrator, help me choose and configure a reusable Search agent baseline. My app is an internal support assistant over SharePoint and indexed PDF policies. Users need grounded answers with citations, permission-aware access, no-answer behavior, and monitoring. Freshness matters for SharePoint content.
```

Expected output:

1. Recommended reconfigurable agent.
2. Route decision and why.
3. Common reconfiguration profile.
4. Pattern-specific configuration gaps.
5. Security, validation, cost, and operations checks.
6. Handoffs.

## 2. Review The Route Decision

The router should choose one of these agents:

| Route | Use When | Follow-Up Agent |
| --- | --- | --- |
| Classic search | The app returns ranked search results directly from indexes. | Classic Search Reconfigurable Agent |
| RAG search | The app retrieves content, assembles prompts, generates answers, and owns citations/no-answer behavior. | RAG Search Reconfigurable Agent |
| Agentic retrieval | Azure AI Search should manage knowledge bases, knowledge sources, planning, references, activity logs, and optional synthesis. | Agentic Retrieval Reconfigurable Agent |
| Mixed | The app needs more than one pattern, such as product search plus a grounded assistant. | Start with the dominant user journey, then configure the second pattern separately. |

If the route feels wrong, give the router one correction. For example:

```text
The app should not generate answers. It should only return ranked product results with facets and autocomplete. Re-route this as classic search.
```

## 3. Configure Classic Search

Use Classic Search Reconfigurable Agent when the app primarily needs direct search results.

Prompt template:

```text
Classic Search Reconfigurable Agent, configure a reusable classic search baseline for this app.

Search experience: [what users search for]
Data sources: [source systems]
Ingestion: [push, indexer, scheduled, near-real-time, unknown]
Query features: [keyword, filters, facets, sorting, geo, autocomplete, synonyms, semantic, vector, hybrid]
Relevance goals: [freshness, boosting, exact match, semantic match, personalization]
Security: [auth, RBAC, tenant boundaries, document-level access]
Special cases: [multilingual, regions, high-cardinality facets, compliance]
Validation: [example queries and expected behavior]
```

Example:

```text
Classic Search Reconfigurable Agent, configure a reusable classic search baseline for a product catalog. Users need keyword search, filters, facets, autocomplete, synonyms, semantic ranking, and region-based access. Data comes from a product API and nightly export. Identify the index schema, ingestion mode, query features, relevance policy, security model, special cases, and validation checks.
```

Expected output:

- classic search fit decision
- baseline configuration
- user-specific reconfiguration points
- index, ingestion, query, and relevance plan
- security and operations notes
- validation checks
- handoffs

## 4. Configure RAG Search

Use RAG Search Reconfigurable Agent when your app owns answer generation over retrieved content.

Prompt template:

```text
RAG Search Reconfigurable Agent, configure a reusable RAG baseline for this app.

User questions: [what users ask]
Data sources: [documents, indexes, source systems]
Answer style: [short answer, detailed answer, quoted answer, structured JSON]
Retrieval mode: [keyword, vector, hybrid, semantic, unknown]
Chunking needs: [document types, structure, citations, long documents]
Embedding needs: [known deployment or unknown]
Grounding policy: [citations, no-answer, unsupported claims, prompt injection]
Security: [auth, RBAC, permission-aware access]
Validation: [sample questions, citation checks, no-answer tests]
```

Example:

```text
RAG Search Reconfigurable Agent, configure a reusable RAG baseline for a support assistant over indexed help articles. Users need grounded answers with citations, hybrid retrieval, no-answer behavior for unsupported questions, and prompt-injection checks. Embedding deployment is not chosen yet. Identify missing inputs and validation checks.
```

Expected output:

- RAG fit decision
- baseline configuration
- user-specific reconfiguration points
- index, chunking, retrieval, and prompt assembly plan
- grounding, citation, and no-answer policy
- security and operations notes
- evaluation checks
- handoffs

## 5. Configure Agentic Retrieval

Use Agentic Retrieval Reconfigurable Agent when Azure AI Search should manage retrieval planning through knowledge bases and knowledge sources.

Prompt template:

```text
Agentic Retrieval Reconfigurable Agent, configure a reusable agentic retrieval baseline for this app.

Agent scenario: [assistant or app behavior]
Knowledge sources: [indexes, SharePoint, Blob Storage, OneLake, web, mixed, unknown]
Source mode: [indexed, remote, mixed, unknown]
Freshness needs: [live, near-real-time, scheduled]
Grounding needs: [references, citations, activity logs, no-answer behavior]
Synthesis needs: [raw retrieval, synthesized answer, unknown]
Security: [permission inheritance, RBAC, Private Link, compliance]
Special cases: [multi-source questions, regulated data, agent-to-agent workflow]
Validation: [sample questions, reference checks, activity-log checks]
```

Example:

```text
Agentic Retrieval Reconfigurable Agent, configure a reusable agentic retrieval baseline for an enterprise policy assistant. Knowledge sources include SharePoint and indexed policy PDFs. I need permission-aware access, references, activity logs, no-answer behavior, and checks for source coverage, latency, and cost.
```

Expected output:

- agentic retrieval fit decision
- baseline configuration
- user-specific reconfiguration points
- knowledge base and knowledge source plan
- indexed vs. remote source decision
- reasoning effort and synthesis notes
- grounding, references, and activity log validation
- security, cost, region, and operations checks
- handoffs

## 6. Fill Missing Inputs

The agents should mark missing inputs instead of inventing them. Common missing inputs include:

| Missing Input | Who Usually Provides It |
| --- | --- |
| `SEARCH_ENDPOINT` | Azure owner or deployment pipeline |
| `SEARCH_INDEX` | Search engineer or implementation plan |
| `KNOWLEDGE_BASE` | Search or Foundry owner |
| `KNOWLEDGE_SOURCES` | Product owner, data owner, or search engineer |
| `EMBEDDING_DEPLOYMENT` | Foundry or Azure OpenAI owner |
| `SECURITY_MODEL` | Security, identity, or platform owner |
| `VALIDATION_PLAN` | Product owner, evaluator, tester, or Monitoring & Evaluation Agent |

Good follow-up prompt:

```text
Here are the missing inputs I can answer: [values]. Keep unknown Azure resources as placeholders and update the configuration plan.
```

## 7. Bring In Shared Specialists

Use shared specialists when the reconfigurable agent identifies cross-cutting concerns.

| Need | Agent |
| --- | --- |
| Endpoint, identity, `.env`, local auth, RBAC | Auth Config Agent |
| Private Link, document-level access, permission inheritance, compliance | Security & Compliance Agent |
| Model deployment, embedding deployment, Foundry endpoint, quota | Foundry Integration Agent |
| Prompt-injection, moderation, grounded-answer safety | Responsible AI Safety Agent |
| Retrieval quality, citations, references, traces, latency, alerts | Monitoring & Evaluation Agent |
| Production readiness, runbooks, cost guardrails, support handoff | Operations Readiness Agent |
| Implementation steps, file edits, tests, command execution | Application Implementation Validation Agent |

Example handoff:

```text
Auth Config Agent, use this reconfigurable Search plan and define the local/dev/prod auth and endpoint configuration. Do not invent secrets. Mark required RBAC roles and missing tenant details.
```

## 8. Turn The Plan Into Implementation Steps

When the configuration plan is stable, use Application Planning Companion Agent to make the work executable.

```text
Application Planning Companion Agent, turn this reconfigurable Search plan into implementation steps. Track owners, files or artifacts to create, validation commands, missing decisions, and the first bounded handoff to Application Implementation Validation Agent.
```

Only use Application Implementation Validation Agent when the step is bounded and has named files or commands.

```text
Application Implementation Validation Agent, execute this approved step: [step]. Target files: [files]. Validation command: [command]. Expected result: [expected result].
```

## 9. Validate The Configuration

Every configured agent should end with validation checks. At minimum, cover:

- representative user queries
- no-result or no-answer behavior
- relevance or retrieval quality
- citation or reference accuracy for generated answers
- activity logs for agentic retrieval when used
- latency and cost checks
- access-control tests
- monitoring and operations readiness

For generated answers, test unsupported questions and prompt-injection attempts before implementation is considered ready.

## Quick Decision Cheat Sheet

| User Says | Start With |
| --- | --- |
| "I need search filters, facets, autocomplete, and relevance tuning." | Classic Search Reconfigurable Agent |
| "I need answers with citations over indexed documents." | RAG Search Reconfigurable Agent |
| "I need knowledge bases, knowledge sources, references, and activity logs." | Agentic Retrieval Reconfigurable Agent |
| "I am not sure whether this is search, RAG, or agentic retrieval." | Azure AI Search Reconfigurable Orchestrator |
| "I need both product search and a support assistant." | Azure AI Search Reconfigurable Orchestrator, then configure each pattern separately |

## Safe Operating Rules

- Do not provide secrets, API keys, or tokens in chat.
- Do not let the agent invent endpoints, index names, model deployments, knowledge base names, regions, quotas, pricing, or test results.
- Keep unknown values as placeholders until the owner provides them.
- Validate retrieval quality before implementation handoff.
- Use the narrowest reconfigurable agent once the route is clear.

## Next Prompt

Start here:

```text
Azure AI Search Reconfigurable Orchestrator, help me choose and configure a reusable Search agent baseline. My app is: [describe your app]. Users need: [describe the desired experience]. Data sources are: [list sources]. Security constraints are: [list constraints].
```
