# Factory Runtime

The Azure Architecture Factory's in-repo adoption of the
[Agent Framework Runtime Pattern](../../docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md).

The factory uses this module to recommend which runtime a newly
generated project should ship:

- `local` — deterministic Python only.
- `agent-framework` — both runtimes, SDK preferred when configured,
  deterministic as fallback.

This is also the authoritative resolver for the orchestrator's
`runtime: auto` argument.

## Why the factory eats its own cooking

The factory prescribes the
[two-runtime pattern](../../docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md) to
every generated project. This module is the factory itself adopting
that pattern so the pattern is continuously exercised in the repo that
publishes it.

| Pattern rule | How this module satisfies it |
|---|---|
| Two runtimes / one API | `LocalProjectClassifier` and `FoundryProjectClassifier` both implement the `ProjectClassifier` protocol. `build_classifier` picks one. |
| Deterministic-contract tools | `FoundryProjectClassifier` delegates the final verdict to `score_brd`; the LLM only surfaces signals, it never changes the recommendation rule. |
| Forward-progress safety net | If the LLM adds no new signal, `classify` returns the deterministic result verbatim. |
| Automated install order | No install needed — falls back cleanly when `agent_framework` is not importable. |

## Usage

```python
from factory_runtime import assess_brd_readiness, classify_brd

result = classify_brd(brd_markdown)
print(result.runtime)       # "local" or "agent-framework"
print(result.signals)       # evidence
print(result.source)        # "local" or "agent-framework"

readiness = assess_brd_readiness(brd_markdown)
print(readiness.classification)          # Auto-Ready | Auto-Ready With Guardrails | Architect Review Required
print(readiness.percentage_score)        # weighted readiness score
print(readiness.clarification_questions) # targeted follow-up prompts
```

To force the SDK runtime:

```bash
$env:FACTORY_AGENT_FRAMEWORK_ENABLED = "1"
$env:FOUNDRY_PROJECT_ENDPOINT = "https://<project>.services.ai.azure.com/api/projects/<name>"
$env:FOUNDRY_MODEL_DEPLOYMENT_NAME = "gpt-5.2"
```

Without those flags (or without the preview SDK installed) the
deterministic local classifier is used.

## Tests

```powershell
python -m pytest scripts/factory_runtime/tests -v
```

The test file enforces the three mandatory test shapes from the
pattern doc: local fallback, SDK selection, forward-progress safety
net.
