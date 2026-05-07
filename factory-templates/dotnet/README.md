# Factory .NET templates

Reusable C# fragments for `lang-dotnet-implementer` to copy into a project's
`src/<service>/` folder when the BRD calls for an Azure AI Foundry agent. All
templates target **net8.0** and authenticate with `DefaultAzureCredential` —
never connection strings or keys.

| Template | Purpose | When to use |
|---|---|---|
| `FoundryAgentWithCodeInterpreter.cs.template` | One-shot Foundry agent runner with `CodeInterpreter` and a single uploaded file. Handles upload, agent version create, invoke, JSON validate/format, version cleanup. | BRD declares an agent that needs sandboxed Python over an attached file (PDF/CSV/XLSX extraction, chart generation, calculations). |
| `FoundryAgentWithFileSearch.cs.template` | Foundry agent runner that uploads N documents into an ephemeral vector store, registers `file_search`, runs the prompt, and tears the store + agent version down. | BRD declares an agent that needs RAG/semantic lookup over a fixed corpus (policies, manuals, knowledge base). |
| `FoundryAgentWithFunctionCalling.cs.template` | Foundry agent runner that registers one or more developer-supplied function tools and runs a bounded tool-call loop (`maxToolHops = 5`) until the model converges. | BRD declares an agent that must call backend services / repositories / external APIs as tools. |
| `FoundrySettings.cs.template` | DI-bindable `FoundrySettings` config object plus a generic result record. | Pair with any of the agent templates above. |

## BRD trigger \u2192 template

`agent-tooling-advisor` (Phase 1.5) emits the canonical `recommended_tools[]`
list per agent. The implementer maps each entry to a template:

| `recommended_tools[].type` | Template |
|---|---|
| `code_interpreter` | `FoundryAgentWithCodeInterpreter.cs.template` |
| `file_search` | `FoundryAgentWithFileSearch.cs.template` |
| `function` (any number, named) | `FoundryAgentWithFunctionCalling.cs.template` |

Multiple tool entries on the same agent collapse into the single richest
template (e.g. one `function_calling` runner that also registers a
`file_search` tool when both are advised). Unknown tool tokens cause the
implementer to halt with an escalation block (mirrors the
unsupported-language guardrail). Add a new
`factory-templates/dotnet/<tool>.template` rather than improvising in-project.

```yaml
implementation:
  language: dotnet
  agents:
    - name: extraction
      role: "Extract structured fields from uploaded contracts."
      input: pdf
      output: json
      tools: [code_interpreter]            # \u2192 FoundryAgentWithCodeInterpreter
      model: gpt-4.1-mini
    - name: policy-lookup
      role: "Answer policy questions over the corporate handbook."
      tools: [file_search]                  # \u2192 FoundryAgentWithFileSearch
    - name: order-router
      role: "Look up and update orders via backend APIs."
      tools: [function]                     # \u2192 FoundryAgentWithFunctionCalling
```

## Token replacement

When scaffolding, replace these placeholders verbatim across all `.template`
files copied into the same service:

| Token | Example | Notes |
|---|---|---|
| `{{NAMESPACE}}` | `OrdersApi.Services` | Match the consuming `.csproj` root namespace. |
| `{{CLASS_NAME}}` | `ExtractionService` | Derive from the agent `name` in the BRD (PascalCase + `Service`). |
| `{{RESULT_TYPE}}` | `ExtractionResult` | Domain-specific result type. Replace in BOTH files. |
| `{{INPUT_PURPOSE_COMMENT}}` | `"Extracts structured contract terms from the uploaded PDF."` | One-line description of the agent's job. Used in the XML doc comment. |

After substitution, drop the `.template` suffix from the filename so the file
becomes a real `.cs` file.

## Required NuGet packages

Add to the consuming `.csproj`:

```xml
<ItemGroup>
  <PackageReference Include="Azure.AI.Projects" Version="2.0.0" />
  <PackageReference Include="Azure.Identity" Version="1.21.0" />
</ItemGroup>
```

(`OpenAI.Files` and `OpenAI.Responses` are transitively referenced via
`Azure.AI.Projects`.)

## RBAC

The compute identity (Container App user-assigned MI by default) needs
`Azure AI User` on the Foundry project. The factory's
`infra/modules/identity/` module exposes this assignment when
`agent.tools` includes `code_interpreter`; do not roll a custom role here.

## Validation

`lang-dotnet-implementer` MUST run `dotnet build` after copying these templates
into a service. The build verifies:

- Token replacement was complete (no residual `{{...}}`).
- Package references compile against net8.0.
- Nullable + warnings-as-errors do not flag the generated file.

If the build fails, the implementer reverts the service and reports per its
standard guardrail.
