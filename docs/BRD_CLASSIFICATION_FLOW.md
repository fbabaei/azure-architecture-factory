# BRD Classification Flow

How the Azure Architecture Factory decides whether a new project should
ship the Microsoft Agent Framework SDK runtime or stay purely
deterministic.

> **Short version:** every BRD that enters the factory is scored for
> LLM signals. The score picks one of two runtime shapes for the
> generated project. The user can always override.

## The cycle

```
BRD arrives
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ scripts/factory_runtime/project_classifier.py       │
│ score_brd(brd_text)                                 │
│                                                     │
│   Positive signals (each adds +1):                  │
│     "foundry", "azure openai", "copilot",           │
│     "chat agent", "chatbot", "llm",                 │
│     "retrieval-augmented", " rag ",                 │
│     "document extraction", "clarification",         │
│     "form filling", "natural language",             │
│     "summariz", "classif", "semantic search",       │
│     "vector search", "embedding", "prompt"          │
│                                                     │
│   Counter-signals (each subtracts 1):               │
│     "etl pipeline", "batch job",                    │
│     "data warehouse", "power bi",                   │
│     "infrastructure automation", "terraform only"   │
│                                                     │
│   score = len(positive) − len(counter)              │
└─────────────────────────────────────────────────────┘
    │
    ▼
  score ≥ 1 ?
    │
    ├── YES ──► runtime = "agent-framework"
    │             → generated project ships BOTH runtimes
    │               (SDK preferred, local as fallback)
    │
    └── NO  ──► runtime = "local"
                  → generated project ships deterministic
                    Python only, no SDK dependency
```

The classifier lives at
[`scripts/factory_runtime/project_classifier.py`](../scripts/factory_runtime/project_classifier.py)
and is itself an adoption of the
[Agent Framework Runtime Pattern](AGENT_FRAMEWORK_RUNTIME_PATTERN.md) —
the factory drinks its own champagne.

## Who runs the classifier

The classifier runs at different points depending on how a BRD enters
the factory:

| Entry point | When the classifier runs | Effect |
|---|---|---|
| **Portal** — BRD uploaded through the web UI | `scripts/local_brd_runner.py::process_brd_document` calls `classify_brd()` on every submission | Result recorded as `suggested_runtime` in `project-manifest.json` and as `suggestedRuntime` in `factory-projects.generated.json`, regardless of orchestrator decisions later |
| **`project-orchestrator` with `Runtime: auto`** *(default)* | Orchestrator calls the classifier | Verdict becomes the resolved runtime; `agent_runtime_source = "auto"` in the manifest |
| **`project-orchestrator` with `Runtime: local`** | Classifier is skipped | Project ships deterministic Python only; `agent_runtime_source = "explicit"` |
| **`project-orchestrator` with `Runtime: agent-framework`** | Classifier is skipped | Project ships both runtimes; `agent_runtime_source = "explicit"` |

User intent always wins. `auto` is a recommendation, not a mandate.

## Two questions the classifier answers

Be explicit about the distinction:

1. **"Does this BRD involve LLM work?"** — this is what the classifier
   actually decides, by looking at the text.
2. **"Should the generated project use the Agent Framework SDK?"** —
   follows deterministically from question 1: the factory's opinion is
   that if you're doing LLM work on Azure, you should use the Agent
   Framework SDK rather than hand-rolling HTTP calls and tool routing.

The classifier's real job is signal detection. The runtime choice is
an obvious function of the signal result.

## What the runtime choice produces

### `runtime = "local"`

The generated project ships:

- FastAPI (or equivalent) + deterministic Python services.
- No `agent-framework-*` dependency. No `azure-ai-agentserver-*` dependency.
- No Foundry credential required at runtime.
- Smaller container image, faster cold start, no preview packages.

Good for ETL, reporting, infrastructure automation, and any backend
that does not involve natural language.

### `runtime = "agent-framework"`

The generated project ships:

- FastAPI with a runtime factory that tries the SDK first, falls back
  to the deterministic local runtime on any failure (import, auth,
  Foundry outage).
- Both a `LocalRuntime` and a `FoundryRuntime` behind the same
  interface. See
  [`factory-templates/agent-framework/foundry_agent_runtime.template.py`](../factory-templates/agent-framework/foundry_agent_runtime.template.py)
  for the complete reference.
- Installer scripts (`scripts/install_agent_framework.ps1` /
  `scripts/install_agent_framework.sh`) so preview-package install
  order is automated, not documented in prose.
- A managed-identity auth path (`DefaultAzureCredential` →
  **Azure AI Developer** role on the Foundry project). No API keys.

Good for chat UX, document extraction, multi-turn clarification or
form-filling, and any workload that depends on Azure AI Foundry or
Azure OpenAI.

## Classifier internals

### Deterministic runtime (always available)

`LocalProjectClassifier.classify(brd_text)` is pure keyword scoring.
It runs in-process, has zero external dependencies, and never needs
credentials. Every factory run uses this at minimum.

### SDK runtime (opt-in, enriches signals)

When these three environment variables are set on the factory runner
or portal container:

```
FACTORY_AGENT_FRAMEWORK_ENABLED=1
FOUNDRY_PROJECT_ENDPOINT=https://<project>.services.ai.azure.com/api/projects/<name>
FOUNDRY_MODEL_DEPLOYMENT_NAME=<deployment>
```

…and the preview SDK is importable, the factory uses
`FoundryProjectClassifier`. This classifier:

1. Runs the deterministic classifier first to establish a floor.
2. Asks an Agent Framework `Agent` to surface any LLM-related signals
   the keyword scanner may have missed (paraphrases, domain-specific
   synonyms).
3. Merges the extra signals but keeps the deterministic verdict.

This enforces the pattern's rule 2: the LLM can enrich reasoning, but
it can never produce a runtime choice the deterministic classifier
could not produce.

### Graceful fallback

Any of these failure modes returns the deterministic classifier
silently, so the factory never goes offline because of a preview
dependency:

- `FACTORY_AGENT_FRAMEWORK_ENABLED` not set.
- `FOUNDRY_PROJECT_ENDPOINT` or `FOUNDRY_MODEL_DEPLOYMENT_NAME` missing.
- `agent_framework` / `agent_framework.foundry` not importable.
- `DefaultAzureCredential` unable to resolve a credential source.
- Any exception during SDK client construction.

## What the manifest looks like afterwards

A project generated with `Runtime: auto` on an LLM-shaped BRD ends up
with, in `project-manifest.json`:

```jsonc
{
  "project": "customer-portal-20260417120000",
  "agent_runtime": "agent-framework",
  "agent_runtime_source": "auto",
  "suggested_runtime": {
    "runtime": "agent-framework",
    "source": "local",
    "score": 3,
    "signals": [
      "Copilot-style experience",
      "RAG pipeline",
      "Azure AI Foundry integration"
    ],
    "counterSignals": [],
    "reasoning": "Detected Copilot-style experience, RAG pipeline, Azure AI Foundry integration — recommending the Agent Framework SDK runtime alongside the deterministic fallback."
  }
}
```

For an ETL-shaped BRD:

```jsonc
{
  "project": "warehouse-loader-20260417120000",
  "agent_runtime": "local",
  "agent_runtime_source": "auto",
  "suggested_runtime": {
    "runtime": "local",
    "source": "local",
    "score": -1,
    "signals": [],
    "counterSignals": ["pure ETL workload"],
    "reasoning": "No LLM-driven components detected in the BRD. The deterministic Python runtime is sufficient; shipping the SDK would add a preview dependency without benefit."
  }
}
```

Both `agent_runtime` (the authoritative choice) and
`suggested_runtime` (the full classifier evidence) are present so
reviewers can audit the decision.

## Overriding the classifier

Every BRD submission through the orchestrator accepts an explicit
`Runtime:` argument. Examples:

```text
# Force deterministic Python even on a chat-heavy BRD
Use the project-orchestrator agent.
Input: docs/BRD.md
Runtime: local

# Force the SDK runtime on a BRD that does not obviously need it
Use the project-orchestrator agent.
Input: docs/BRD.md
Runtime: agent-framework

# Let the factory decide (default)
Use the project-orchestrator agent.
Input: docs/BRD.md
Runtime: auto
```

When the user passes an explicit value, the classifier is skipped for
the runtime decision but still runs through the portal code path so
`suggested_runtime` is still recorded for auditability.

## Related docs

- [QUICKSTART.md](QUICKSTART.md) — the one-page overview of the
  factory, including the runtime decision table.
- [AGENT_FRAMEWORK_RUNTIME_PATTERN.md](AGENT_FRAMEWORK_RUNTIME_PATTERN.md)
  — the four rules every project adopting the SDK must follow.
- [`scripts/factory_runtime/README.md`](../scripts/factory_runtime/README.md)
  — implementation notes for the classifier module itself.
- [`factory-templates/agent-framework/README.md`](../factory-templates/agent-framework/README.md)
  — the reusable files a generated project copies when `runtime =
  agent-framework`.
