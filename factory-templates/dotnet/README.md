# Factory .NET templates

Reusable C# fragments for `lang-dotnet-implementer` to copy into a project's
`src/<service>/` folder when the BRD calls for an Azure AI Foundry agent. All
templates target **net8.0** and authenticate with `DefaultAzureCredential` —
never connection strings or keys.

| Template | Purpose | When to use |
|---|---|---|
| `FoundryAgentWithCodeInterpreter.cs.template` | One-shot Foundry agent runner with `CodeInterpreter` and a single uploaded file. Handles upload, agent version create, invoke, JSON validate/format, version cleanup. | BRD declares an agent that needs sandboxed Python over an attached file (PDF/CSV/XLSX extraction, chart generation, calculations). |
| `FoundrySettings.cs.template` | DI-bindable `FoundrySettings` config object plus a generic result record. | Pair with `FoundryAgentWithCodeInterpreter.cs.template`. |

## BRD trigger

The implementer copies these templates when an entry under
`implementation.agents[]` declares `code_interpreter` in `tools`:

```yaml
implementation:
  language: dotnet
  agents:
    - name: extraction
      role: "Extract structured fields from uploaded contracts."
      input: pdf
      output: json
      tools: [code_interpreter]            # <-- triggers this template
      model: gpt-4.1-mini
```

`tools` is an open vocabulary; `code_interpreter` is the only token currently
backed by a template. Unknown tool names cause the implementer to halt with an
escalation block (mirrors the unsupported-language guardrail).

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
