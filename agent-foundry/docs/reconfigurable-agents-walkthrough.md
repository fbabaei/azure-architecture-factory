# Reconfigurable Agents Walkthrough

This walkthrough shows how a new user can use the Azure AI Search prebuilt reconfigurable agents from a rough app idea to a final handoff package.

The example uses a mock project named Contoso Support Assistant.

## Mock Project

Contoso wants an internal support assistant for support engineers.

The assistant should answer questions such as:

```text
How do I troubleshoot device sync failures?
```

Contoso has these knowledge sources:

- product support articles in Azure AI Search
- policy PDFs in Blob Storage
- internal SharePoint troubleshooting documents

The app needs:

- grounded answers
- citations
- no guessing when sources do not support an answer
- permission-aware access
- support for questions that may need content from more than one source

## Step 1: Describe The User Need

Start by describing what the application user is trying to do. Do not start with Azure resource names or model names unless you already know them.

Example prompt:

```text
Azure AI Search Reconfigurable Orchestrator, help me choose and configure a reusable Search agent baseline.

My app is Contoso Support Assistant. Support engineers ask troubleshooting questions over product support articles, policy PDFs, and SharePoint troubleshooting docs. They need grounded answers with citations, no-answer behavior when sources do not support a response, and permission-aware access.
```

Expected understanding:

```text
We are trying to find the right search agent for the app based on what the app needs to do.
```

## Step 2: Ask The Router To Choose

The router is Azure AI Search Reconfigurable Orchestrator. Its job is to decide whether the request fits classic search, RAG search, agentic retrieval, or a mixed pattern.

For this project, the important clues are:

- the user wants generated answers
- the answers must be grounded
- citations are required
- unsupported questions should not be guessed

That points toward RAG search.

## Step 3: Choose RAG Instead Of Classic Search

Classic search is best when the app returns ranked documents, records, filters, facets, autocomplete, or direct search results.

RAG search is best when the app retrieves content and then generates an answer grounded in that retrieved content.

For Contoso, the right choice is:

```text
RAG Search Reconfigurable Agent
```

Reason:

```text
The user is asking for grounded answers with citations, not only ranked search results.
```

## Step 4: Check Whether Agentic Retrieval Is Needed

Agentic retrieval is useful when Azure AI Search should manage knowledge bases, knowledge sources, query planning, query decomposition, references, activity logs, or optional synthesis.

For the Contoso example, the requirement does not explicitly ask Azure AI Search to manage query decomposition or knowledge-base orchestration. The app can own retrieval, prompt assembly, generated answers, citations, and no-answer behavior.

So the route remains:

```text
RAG Search Reconfigurable Agent
```

## Step 5: Configure The RAG Agent

Ask the selected agent to produce a configuration contract.

Example prompt:

```text
RAG Search Reconfigurable Agent, configure a reusable RAG baseline for Contoso Support Assistant.

Users ask troubleshooting questions. Data sources include Azure AI Search support articles, Blob Storage policy PDFs, and SharePoint troubleshooting docs. The app needs grounded answers with citations, hybrid retrieval if appropriate, permission-aware access, no-answer behavior, and validation checks for answer quality, citations, and security.
```

The agent should focus on these configuration areas:

```text
retrieval, chunking, grounding, citations, security, and validation
```

## Step 6: Identify Missing Inputs

The agent should not invent real Azure values. Missing inputs are a safety feature.

Example missing inputs:

```text
Missing inputs:
- SEARCH_ENDPOINT
- SEARCH_INDEX
- EMBEDDING_DEPLOYMENT
- CHAT_MODEL_DEPLOYMENT
- SECURITY_MODEL
- CITATION_FIELDS
- FRESHNESS_POLICY
```

Why this matters:

```text
Inventing missing values may be inaccurate and can lead to the wrong design or unsafe implementation.
```

## Step 7: Fill The Configuration Contract

The configuration contract is a structured form. The project team fills it with real values and decisions.

Example filled contract:

```text
RAG configuration:
- SEARCH_ENDPOINT: <contoso-search-endpoint>
- SEARCH_INDEX: support-knowledge-index
- DATA_SOURCES:
  - Azure AI Search index for support articles
  - Blob Storage PDFs for policy documents
  - SharePoint troubleshooting docs
- RETRIEVAL_MODE: hybrid search
- CHUNKING_POLICY: 800-token chunks with 150-token overlap
- GROUNDING_POLICY: answer only from retrieved sources
- CITATIONS: include article title, document URL, and page number when available
- SECURITY_MODEL: filter results by user's group permissions
- NO_ANSWER_BEHAVIOR: say when the answer is not found in the sources
- VALIDATION_PLAN: test answer quality, citations, and permission filtering
```

The key idea:

```text
The agent's contract is a structured form that the project fills with real values and decisions.
```

## Step 8: Turn The Contract Into An Implementation Plan

The contract defines configuration. The implementation plan defines what must be built, connected, or tested.

Example implementation plan:

```text
Implementation plan:
1. Create or confirm Azure AI Search index: support-knowledge-index
2. Ingest support articles, policy PDFs, and SharePoint docs
3. Chunk documents using the selected chunking policy
4. Generate embeddings for each chunk
5. Configure hybrid retrieval over keyword + vector search
6. Add permission filters so users only see allowed content
7. Build answer generation using retrieved chunks only
8. Return citations with title, URL, and page number
9. Add no-answer behavior when sources do not support an answer
10. Validate with test questions, citation checks, and security checks
```

Important distinction:

```text
The contract defines the configuration. The implementation plan defines what needs to be built or connected.
```

## Step 9: Validate The Configuration

A configuration can look correct and still fail in practice. Validation proves whether it works for real user questions.

Validate at least these areas:

```text
1. Retrieval quality
2. Grounding
3. Citations
4. Security
```

Example validation checks:

- Ask representative troubleshooting questions.
- Confirm the retrieved chunks contain enough support for the generated answer.
- Confirm citations point to the right source documents.
- Ask unsupported questions and confirm the app does not guess.
- Confirm users cannot retrieve content they do not have permission to access.

## Step 10: Iterate Or Ship

If validation fails, adjust the configuration and validate again.

Examples:

- If answers miss important policy content, adjust sources or retrieval mode.
- If citations are weak, improve citation fields and chunk metadata.
- If users see restricted content, fix the security model before continuing.
- If no-answer behavior is too eager or too weak, adjust the grounding policy.

The loop is:

```text
Configure -> Implement -> Validate -> Improve -> Validate again
```

## Step 11: Produce The Final Handoff Package

At the end, hand off a package containing:

```text
- selected agent
- configuration contract
- implementation plan
- validation results
- known limitations
```

For Contoso, the final handoff could look like this:

```text
Final handoff:
- Selected agent: RAG Search Reconfigurable Agent
- Reason: grounded answers with citations over support knowledge
- Configuration contract: completed
- Implementation plan: completed
- Environment values: listed or linked safely
- Security rules: documented
- Validation results: passed or listed with failures
- Known limitations: documented
- Next owner: implementation or operations team
```

## What You Should Remember

The reconfigurable agent flow is:

```text
Describe the need
  -> route to the right agent
  -> configure the selected baseline
  -> identify missing inputs
  -> fill the contract
  -> create the implementation plan
  -> validate behavior
  -> iterate or hand off
```

For Contoso Support Assistant, RAG search is the best fit because the app needs generated grounded answers with citations and no-answer behavior.
