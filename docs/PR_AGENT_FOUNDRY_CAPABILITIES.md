# feat: declare Foundry capabilities on AAF agents + add .NET Code Interpreter templates

## Description

Adds a forward-looking `foundry_capabilities` declaration to every AAF agent's YAML front matter, documenting which Azure AI Foundry tools (`code_interpreter`, `file_search`, `function_calling`) each agent should be wired to **if/when** it is migrated from Copilot runtime to a Foundry-hosted agent. Today this metadata is advisory — the active runtime contract remains the existing `tools:` field.

Also lands the `factory-templates/dotnet/` Code Interpreter pattern (template + settings + README) so projects whose BRD declares `tools: [code_interpreter]` have a ready-to-copy .NET 8 implementation. Agent contracts for `lang-dotnet-implementer` and `project-orchestrator` are extended to recognize the new BRD token and the template path.

## Related Issue

Internal — no tracking issue.

## What Changed

- **Agent metadata** — `.github/agents/*.agent.md` (19 files): added `foundry_capabilities: [...]` alongside existing `tools:` field. No runtime behavior change.
- **Agent contracts** — `lang-dotnet-implementer.agent.md`, `project-orchestrator.agent.md`: documented Code Interpreter wiring path, BRD `tools[]` token resolution, and human-review halt for unknown tokens.
- **Documentation** — `.github/agents/README.md`: appended **Foundry Capabilities (Forward-Looking)** section with token→SDK mapping, full recommendation matrix, and orchestrator consumption rules.
- **.NET templates (new)** — `factory-templates/dotnet/`:
  - `FoundryAgentWithCodeInterpreter.cs.template` — `AIProjectClient` + `OpenAIFileClient.UploadFile` + `DeclarativeAgentDefinition` with `ResponseTool.CreateCodeInterpreterTool`, JSON fence stripping, agent version cleanup in `finally`.
  - `FoundrySettings.cs.template` — `FoundrySettings` + generic result type.
  - `README.md` — token table, NuGet refs, BRD trigger example, RBAC delegation note.

## Requirements Coverage

| Requirement | Implementation | Validated by |
| --- | --- | --- |
| Each agent declares which Foundry tools it should be granted upon migration | `foundry_capabilities` field in 19 `.github/agents/*.agent.md` | `pytest` (148/148) — no regressions in YAML parsing |
| Recommendation matrix is discoverable in one place | `.github/agents/README.md` — *Foundry Capabilities (Forward-Looking)* section | manual review; markdown renders correctly |
| `code_interpreter` BRD token has a ready .NET implementation pattern | `factory-templates/dotnet/FoundryAgentWithCodeInterpreter.cs.template` + `FoundrySettings.cs.template` | template README documents required NuGet refs (`Azure.AI.Projects 2.0.0`, `Azure.Identity 1.21.0`) |
| `lang-dotnet-implementer` knows how to consume the template | `.github/agents/lang-dotnet-implementer.agent.md` — *Azure AI Foundry agents (Code Interpreter)* subsection | manual review |
| `project-orchestrator` recognizes BRD `agents[].tools` and halts on unknown tokens | `.github/agents/project-orchestrator.agent.md` — *Resolve agent tooling* block | manual review |

## Files Changed

- `.github/agents/README.md`
- `.github/agents/azure-architecture-implementer.agent.md`
- `.github/agents/azure-project-deployer.agent.md`
- `.github/agents/bicep-infrastructure-validator.agent.md`
- `.github/agents/brd-to-architecture-diagram.agent.md`
- `.github/agents/drawio-architecture-reader.agent.md`
- `.github/agents/factory-handoff.agent.md`
- `.github/agents/factory-workflow-guide.agent.md`
- `.github/agents/lang-dotnet-implementer.agent.md`
- `.github/agents/modernization-to-factory.agent.md`
- `.github/agents/production-environment-advisor.agent.md`
- `.github/agents/project-cost-analyzer.agent.md`
- `.github/agents/project-observability-advisor.agent.md`
- `.github/agents/project-orchestrator.agent.md`
- `.github/agents/project-state-manager.agent.md`
- `.github/agents/project-traceability-advisor.agent.md`
- `.github/agents/repo-change-agent.agent.md`
- `.github/agents/security-compliance-auditor.agent.md`
- `.github/agents/source-code-maintainer.agent.md`
- `.github/agents/terraform-infrastructure-validator.agent.md`
- `factory-templates/dotnet/FoundryAgentWithCodeInterpreter.cs.template` (new)
- `factory-templates/dotnet/FoundrySettings.cs.template` (new)
- `factory-templates/dotnet/README.md` (new)

## Validation

- `python -m pytest` — **148/148 passing** (~15.3s). `factory-templates/` is excluded from collection by `pytest.ini`, and the agent YAML edits are additive front-matter fields that do not affect any Python code path.
- Manual review — all 19 agent files retain a valid YAML front-matter block; new `foundry_capabilities` line placed adjacent to existing `tools:` line.

## Scope

- Does **not** migrate any agent to Foundry runtime. The new field is metadata only.
- Does **not** include the older Tier 1+2 working-tree changes (`factory-templates/sql/`, `factory-templates/pr/`, `infra/modules/data/sql-database.*`, `.github/copilot-instructions.md`) — those will land in a separate focused PR.
- Does **not** include unrelated portal / test-fixture work currently in the working tree.

## Checklist

- [x] Targets the project's declared runtime (.NET 8 LTS for templates).
- [x] No secrets, SQL logins, or connection strings in source.
- [x] AAD / managed identity used (`DefaultAzureCredential` in template).
- [x] Idempotent — agent version cleanup in `finally` block.
- [x] Build clean, tests green; results pasted in **Validation**.
- [x] BRD / architecture diagram unaffected (metadata-only change).
