# Foundry Agent Tooling Advisory — End-to-End Flow

This document describes how the Azure Architecture Factory (AAF) decides which Foundry capabilities (`code_interpreter`, `file_search`, `function_calling`), tools, and baseline prompts to recommend for each Azure AI Foundry agent in a generated project, across all supported intake paths (BRD-driven, diagram-only, or hybrid).

The flow is owned by `project-orchestrator` and delegates to two specialist agents:

- [`brd-to-architecture-diagram`](../.github/agents/brd-to-architecture-diagram.agent.md) — owns Phase 1 architecture and the new `synthesize-agents` mode.
- [`agent-tooling-advisor`](../.github/agents/agent-tooling-advisor.agent.md) — owns Phase 1.5 capability/tool/prompt recommendations. **READ-ONLY**.

## Phase 0–1: Intake & Architecture

1. **User invokes `project-orchestrator`** with one of:
   - BRD/PRD path (`requirements: BRD.md`)
   - Inline prompt
   - `existing-diagram: <path>` (skip MCP generation)
2. **Phase 0** — `project-state-manager` creates `projects/<slug>/` with manifest + logs.
3. **Phase 1** — branches by mode:
   - **Mode A (generate)** — `brd-to-architecture-diagram` runs the MCP Draw.io workflow and produces `<slug>.drawio` + `<slug>.md`.
   - **Mode B (import)** — copies the supplied diagram → extracts components → writes companion notes → sets `diagram_source: "imported"`.

## Phase 1 → 1.5 Bridge: Agent Source Resolution

4. **In Mode B only**, the orchestrator checks: does the BRD declare `implementation.agents[]`?
   - **Yes** → skip synthesis, jump to step 7.
   - **No / no BRD** → call `brd-to-architecture-diagram` in **`synthesize-agents`** mode.
5. **Synthesis pass** scans the `.drawio` XML:
   - Matches shape styles containing `azure-ai-foundry`, `azure-openai`, or `cognitive-services`.
   - Matches labels matching `/agent|assistant|copilot|bot|extractor|classifier/i`.
   - Skips generic rectangles (`api`, `service-1`, etc.) → adds them to `warnings[]`.
   - For each match emits an entry: `{ name, service, description, inbound_edges, outbound_edges, confidence, evidence }`.
   - Confidence is `medium` only when BRD prose corroborates the shape; otherwise `low`.
   - Writes `projects/<slug>/docs/agents/agents-draft.json`.
6. **Orchestrator surfaces the draft** to the user for confirm/edit. The BRD on disk is never modified — the draft is a sidecar.

## Phase 1.5: Agent Tooling Advisory

7. **Skip-or-run gate** — `project-orchestrator` runs `agent-tooling-advisor` if EITHER:
   - `BRD.implementation.agents[]` is non-empty, OR
   - `projects/<slug>/docs/agents/agents-draft.json` exists.

   Otherwise skip → Phase 2.
8. **Advisor source-of-truth resolution**:
   - BRD agents present → use BRD, normal confidence.
   - Only draft present → use draft, **downgrade every confidence by one step** (`high`→`medium`, `medium`→`low`, `low` stays `low`).
9. **Per-agent analysis** (4 internal steps):
   - **Classify intent** from BRD/draft wording → maps to Foundry capabilities (`code_interpreter`, `file_search`, `function_calling`).
   - **Cross-check diagram edges** → which inbound/outbound services suggest which `function` tools.
   - **Draft baseline prompt** (≤1200 chars; lists tools, surfaces compliance constraints).
   - **Score confidence** (`high` / `medium` / `low`).
10. **Validate tool feasibility**:
    - For each `function` tool, check whether a backing factory template exists. Today only `code_interpreter` has a .NET template at `factory-templates/dotnet/FoundryAgentWithCodeInterpreter.cs.template`.
    - Missing template + `strict: true` → `next_action: "block"`.
11. **Write outputs** to `projects/<slug>/docs/agents/`:
    - `agent-tooling.json` (machine-readable)
    - `agent-tooling.md` (human-readable)

## Phase 1.5 → Phase 2 Decision Gate

12. The advisor returns `next_action`:
    - **`block`** → orchestrator halts and surfaces critical findings (typically a missing template).
    - **`needs_review`** → orchestrator presents low-confidence agents to the user and awaits confirmation. *Diagram-only intakes always land here* by design.
    - **`proceed`** → orchestrator loads `agent-tooling.json` into memory.

## Phase 2: Implementation

13. The orchestrator routes by `BRD.implementation.language`:
    - `python` → `azure-architecture-implementer`
    - `dotnet` → `lang-dotnet-implementer`
14. **Forwards advisor output**: each agent's `recommended_tools` becomes the resolved `tools[]` (overriding any missing BRD declaration); `baseline_prompt` becomes the agent instructions in scaffolded code.
15. The language specialist generates Foundry agent code, registering capabilities and stub tool functions.

## Phase 2.5+ → Onward

16. Standard gates continue: alignment convergence (2.5), security (2.6), error-handling (2.7), scalability (2.8), test convergence (3.7), infra validation, deployment, observability.

## Decision matrix

| Intake | Synthesis runs? | Phase 1.5 runs? | Confidence ceiling | Default `next_action` |
|---|---|---|---|---|
| BRD with `agents[]` | No | Yes | `high` | `proceed` |
| BRD without `agents[]` + Foundry shapes in diagram | Yes | Yes (after user confirms draft) | `medium` | `needs_review` |
| `existing-diagram:` only + Foundry shapes | Yes | Yes (after user confirms draft) | `medium` | `needs_review` |
| BRD without `agents[]` + no Foundry shapes | Yes (returns empty) | No | — | `skipped` |
| Pure repo intake, no diagram, no BRD agents | No | No | — | `skipped` |

## Guardrails

- The BRD on disk is **never** modified. Diagram-synthesized agents land in a sidecar file.
- Generic shapes (`api`, `service-1`, unlabeled rectangles) are skipped, with `warnings[]` entries — they are never invented as agents.
- `medium` is the highest possible confidence on the diagram-only path; `high` requires BRD corroboration.
- Tools without a backing factory template halt the language specialist (no silent fallbacks).
- The advisor is read-only: it never edits source, infra, or BRD — only emits the recommendation report.

## Related documents

- [AAF_AGENT_SCOPING.md](AAF_AGENT_SCOPING.md) — 3-tier scoping model and contract validation.
- [.github/agents/README.md](../.github/agents/README.md) — Foundry capability matrix and agent ownership table.
- [factory-templates/dotnet/README.md](../factory-templates/dotnet/README.md) — Code Interpreter template usage.
