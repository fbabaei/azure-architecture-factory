# Agent Framework Runtime Pattern

A factory convention for adding **Microsoft Agent Framework SDK**-backed
agents to generated projects while preserving the deterministic
behaviour the factory guarantees.

## Status
- Pattern adopted: 2026-04-17
- Reference implementation: [`projects/mdr-support-20260416174652/`](../projects/mdr-support-20260416174652/)
- Canonical template: [`factory-templates/agent-framework/`](../factory-templates/agent-framework/)

## When to apply this pattern

Apply when a generated project has any of:

- A chat / conversational UX that requires natural-language understanding.
- An extraction step that turns unstructured documents into structured data.
- A multi-turn clarification or form-filling loop.
- A need for managed-identity authentication to Azure AI Foundry.

Do **not** apply to pure ETL, reporting, or infrastructure-automation
projects. Deterministic Python remains the right choice there.

## The four rules

### 1. Two runtimes, one API surface

Every project that adopts the pattern has two interchangeable agent
runtimes behind the same FastAPI (or equivalent) interface:

| Runtime | Default? | When used |
|---|---|---|
| **Local deterministic** | Yes | Always available; used when SDK / Foundry are not configured or the SDK is not installed |
| **Foundry SDK** | Opt-in | Used when `AGENT_FRAMEWORK_ENABLED=1` plus `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL_DEPLOYMENT_NAME` are set *and* the SDK imports succeed |

The runtime factory tries the SDK runtime first and gracefully falls
back to the local runtime on `ImportError` or `RuntimeError`. The
service stays online even if Foundry is down.

### 2. Deterministic contract, LLM interpretation

Every SDK tool function **must** delegate state mutation to a pure
Python helper that already exists in the project. The LLM decides
*which* tool/field to invoke; the helper decides *how* the underlying
state changes.

```
LLM (Agent Framework)  ──calls──►  tool function
                                         │
                                         ▼
                            deterministic project helper
                                         │
                                         ▼
                              repository / audit log
```

This guarantees the SDK runtime can never produce state the
deterministic runtime could not produce. Schema validation, audit
logging, and persistence are identical across both runtimes.

### 3. Forward-progress safety net

Multi-turn loops (clarification, form-filling, negotiation) must have a
hard forward-progress guarantee. The pattern:

```
pre_state  = compute_progress_set(state)
try:
    run_sdk_agent(prompt)            # LLM may or may not call tools
except Exception:
    log_and_continue()
post_state = compute_progress_set(state)

if post_state == pre_state:
    apply_deterministic_step(state)   # safety net - always advances
```

If the LLM returns without calling a tool, or calls tools that do not
shrink the missing-fields set, the deterministic helper is invoked so
the loop always advances. The project's state machine is the floor;
the LLM is an optimisation on top.

### 4. Install order is automated, not documented

The preview SDK packages are install-order-sensitive. Projects do not
document the order in prose; they ship the canonical installer scripts:

```
scripts/install_agent_framework.ps1   # Windows
scripts/install_agent_framework.sh    # Linux / CI
```

Both scripts are copied verbatim from
[`factory-templates/agent-framework/`](../factory-templates/agent-framework/).
`README.md`, `DEPLOY.md`, and `requirements.txt` all point at the
scripts rather than inlining pip commands.

## Required env flags

| Flag | Required | Default | Purpose |
|---|---|---|---|
| `AGENT_FRAMEWORK_ENABLED` | Yes | unset | Opt-in master switch |
| `FOUNDRY_PROJECT_ENDPOINT` | Yes | unset | Full `https://<project>.services.ai.azure.com/api/projects/<project>` URL |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME` | Yes | unset | Azure AI Foundry model deployment name (e.g. `gpt-5.2`) |

The project's `Settings` dataclass must expose a derived
`foundry_runtime_enabled` property that is true only when all three
values are populated. The runtime factory reads this property — never
the individual env vars — so test seams stay clean.

## RBAC & infra requirements

Projects adopting this pattern need:

- A user-assigned managed identity on the Container App.
- The managed identity granted **Azure AI Developer** on the Foundry
  project (scoped, not subscription-wide).
- `DefaultAzureCredential` as the auth path in code (no API keys).

Bicep modules for this live under the project's own `infra/` folder;
the factory does not currently publish a shared module for the AI
Developer role assignment, but may in a future iteration.

## Testing expectations

Projects adopting the pattern must have:

1. A test that proves the factory falls back to the local runtime when
   the SDK is not configured.
2. A test that proves the factory selects the SDK runtime when the SDK
   is installed *and* the env flags are set — branching on
   `importlib.util.find_spec("agent_framework")` so CI passes in both
   environments.
3. A test that proves the forward-progress safety net fires when the
   LLM stalls (using a no-op stub agent).

See the MDR project's `tests/test_generated_project.py` for worked
examples: `test_agent_runtime_selects_foundry_when_enabled`,
`test_apply_answer_to_arrangement_public_alias_matches_legacy`, and
`test_foundry_clarification_driver_falls_back_when_llm_stalls`.

## How the factory applies this pattern

The factory agents are aware of the convention:

- [`azure-architecture-implementer`](../.github/agents/azure-architecture-implementer.agent.md)
  scaffolds the SDK runtime when the diagram contains an LLM-driven
  component (chat UX, extraction, clarification loop) by copying
  `factory-templates/agent-framework/` into the project.
- [`project-orchestrator`](../.github/agents/project-orchestrator.agent.md)
  instructs the implementer to adopt this pattern during Phase 2 when
  Azure AI Foundry or any LLM component is present in the target
  architecture.

The reference implementation in `projects/mdr-support-20260416174652/`
stays the authoritative worked example. Updates to the pattern should
land there first, prove out through the project's test suite, then be
promoted back into `factory-templates/agent-framework/`.

## Why not just bake the SDK into every project

1. **Preview packages.** `agent-framework-*` is rc6 and
   `azure-ai-agentserver-*` is beta. Not every generated project should
   carry a preview dependency.
2. **Not every project needs an LLM.** ETL, infra automation, and
   reporting projects stay cheaper and more predictable on
   deterministic Python.
3. **Graceful adoption.** Projects can ship the local runtime on day 1
   and flip the env flag later without a rewrite.
