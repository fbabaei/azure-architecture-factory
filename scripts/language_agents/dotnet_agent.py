""".NET 8 / ASP.NET Core language specialist.

Emits a minimal API project with xUnit + FluentAssertions tests, a multi-stage
Dockerfile, and global.json pinning the SDK. Mirrors the Python agent's
structure so the runner flow is identical for both languages.

Layout:
    src/{ProjectName}.csproj
    src/Program.cs
    src/appsettings.json
    src/appsettings.Development.json
    src/Dockerfile
    src/.dockerignore
    tests/{ProjectName}.Tests.csproj
    tests/HealthEndpointTests.cs
    global.json
    README.md
    DEPLOY.md
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import LanguageAgent, LanguageEmitContext, LanguageEmitResult


def _dotnet_project_name(title: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", title)
    pascal = "".join(p[:1].upper() + p[1:].lower() for p in parts if p)
    return pascal or "GeneratedApi"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _build_csproj(enable_observability: bool) -> str:
    observability_pkg = (
        "    <PackageReference Include=\"Microsoft.ApplicationInsights.AspNetCore\" Version=\"2.23.0\" />\n"
        if enable_observability
        else ""
    )
    return (
        "<Project Sdk=\"Microsoft.NET.Sdk.Web\">\n\n"
        "  <PropertyGroup>\n"
        "    <TargetFramework>net8.0</TargetFramework>\n"
        "    <Nullable>enable</Nullable>\n"
        "    <ImplicitUsings>enable</ImplicitUsings>\n"
        "    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>\n"
        "    <InvariantGlobalization>false</InvariantGlobalization>\n"
        "  </PropertyGroup>\n\n"
        "  <ItemGroup>\n"
        "    <PackageReference Include=\"Microsoft.AspNetCore.OpenApi\" Version=\"8.0.10\" />\n"
        "    <PackageReference Include=\"Swashbuckle.AspNetCore\" Version=\"6.8.1\" />\n"
        "    <PackageReference Include=\"Azure.Identity\" Version=\"1.13.1\" />\n"
        "    <PackageReference Include=\"Microsoft.Extensions.Azure\" Version=\"1.7.6\" />\n"
        f"{observability_pkg}"
        "  </ItemGroup>\n\n"
        "</Project>\n"
    )


def _build_program(title: str, enable_observability: bool) -> str:
    safe_title = title.replace("\"", "'")
    observability_block = (
        "// Application Insights — reads APPLICATIONINSIGHTS_CONNECTION_STRING from env.\n"
        "builder.Services.AddApplicationInsightsTelemetry();\n"
        if enable_observability
        else ""
    )
    return (
        "using Microsoft.AspNetCore.Mvc;\n\n"
        "var builder = WebApplication.CreateBuilder(args);\n\n"
        "builder.Services.AddEndpointsApiExplorer();\n"
        "builder.Services.AddSwaggerGen();\n"
        "builder.Services.AddProblemDetails();\n"
        f"{observability_block}"
        "\n"
        "var app = builder.Build();\n\n"
        "if (app.Environment.IsDevelopment())\n"
        "{\n"
        "    app.UseSwagger();\n"
        "    app.UseSwaggerUI();\n"
        "}\n\n"
        "app.UseExceptionHandler();\n\n"
        "// Liveness probe\n"
        "app.MapGet(\"/health\", () => Results.Ok(new\n"
        "{\n"
        "    status = \"ok\",\n"
        "    timestamp = DateTimeOffset.UtcNow\n"
        "}));\n\n"
        "// Readiness probe\n"
        "app.MapGet(\"/health/ready\", () => Results.Ok(new\n"
        "{\n"
        "    status = \"ready\",\n"
        "    timestamp = DateTimeOffset.UtcNow\n"
        "}));\n\n"
        "// Starter endpoint — replace with workload-specific logic.\n"
        "var api = app.MapGroup(\"/api\");\n"
        "api.MapPost(\"/ask\", ([FromBody] AskRequest payload) =>\n"
        "{\n"
        "    var summary = (payload.Context ?? string.Empty).Trim();\n"
        "    if (summary.Length > 240) summary = summary[..240];\n"
        "    var answer = summary.Length > 0\n"
        "        ? $\"Starter response for question: '{payload.Question}'. Context summary: {summary}. Replace this logic with your workload-specific orchestration.\"\n"
        "        : $\"Starter response for question: '{payload.Question}'. Replace this logic with your workload-specific orchestration.\";\n"
        "    return Results.Ok(new AskResponse(answer, \"generated-starter\"));\n"
        "})\n"
        ".WithName(\"Ask\")\n"
        ".WithOpenApi();\n\n"
        f"app.Logger.LogInformation(\"Starting generated API: {safe_title}\");\n"
        "app.Run();\n\n"
        "public partial class Program { }\n\n"
        "public record AskRequest(string Question, string? Context);\n"
        "public record AskResponse(string Answer, string Source);\n"
    )


def _build_appsettings() -> str:
    return (
        "{\n"
        "  \"Logging\": {\n"
        "    \"LogLevel\": {\n"
        "      \"Default\": \"Information\",\n"
        "      \"Microsoft.AspNetCore\": \"Warning\"\n"
        "    }\n"
        "  },\n"
        "  \"AllowedHosts\": \"*\"\n"
        "}\n"
    )


def _build_appsettings_dev() -> str:
    return (
        "{\n"
        "  \"Logging\": {\n"
        "    \"LogLevel\": {\n"
        "      \"Default\": \"Debug\",\n"
        "      \"Microsoft.AspNetCore\": \"Information\"\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


def _build_dockerfile(project_name: str) -> str:
    return (
        "# syntax=docker/dockerfile:1.7\n"
        "FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build\n"
        "WORKDIR /src\n"
        f"COPY [\"{project_name}.csproj\", \"./\"]\n"
        "RUN dotnet restore\n"
        "COPY . .\n"
        "RUN dotnet publish -c Release -o /app /p:UseAppHost=false\n\n"
        "FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final\n"
        "WORKDIR /app\n"
        "COPY --from=build /app ./\n"
        "ENV ASPNETCORE_URLS=http://+:8080\n"
        "ENV DOTNET_RUNNING_IN_CONTAINER=true\n"
        "EXPOSE 8080\n"
        f"ENTRYPOINT [\"dotnet\", \"{project_name}.dll\"]\n"
    )


def _build_dockerignore() -> str:
    return (
        "bin/\n"
        "obj/\n"
        "*.user\n"
        "*.suo\n"
        ".vs/\n"
        ".idea/\n"
        "node_modules/\n"
        ".git/\n"
        ".github/\n"
        ".venv/\n"
        "tests/\n"
    )


def _build_test_csproj(project_name: str) -> str:
    return (
        "<Project Sdk=\"Microsoft.NET.Sdk\">\n\n"
        "  <PropertyGroup>\n"
        "    <TargetFramework>net8.0</TargetFramework>\n"
        "    <Nullable>enable</Nullable>\n"
        "    <ImplicitUsings>enable</ImplicitUsings>\n"
        "    <IsPackable>false</IsPackable>\n"
        "  </PropertyGroup>\n\n"
        "  <ItemGroup>\n"
        "    <PackageReference Include=\"Microsoft.NET.Test.Sdk\" Version=\"17.11.1\" />\n"
        "    <PackageReference Include=\"xunit\" Version=\"2.9.2\" />\n"
        "    <PackageReference Include=\"xunit.runner.visualstudio\" Version=\"2.8.2\" />\n"
        "    <PackageReference Include=\"FluentAssertions\" Version=\"6.12.2\" />\n"
        "    <PackageReference Include=\"Microsoft.AspNetCore.Mvc.Testing\" Version=\"8.0.10\" />\n"
        "  </ItemGroup>\n\n"
        "  <ItemGroup>\n"
        f"    <ProjectReference Include=\"..\\src\\{project_name}.csproj\" />\n"
        "  </ItemGroup>\n\n"
        "</Project>\n"
    )


def _build_test_program() -> str:
    return (
        "using System.Net;\n"
        "using FluentAssertions;\n"
        "using Microsoft.AspNetCore.Mvc.Testing;\n"
        "using Xunit;\n\n"
        "public class HealthEndpointTests : IClassFixture<WebApplicationFactory<Program>>\n"
        "{\n"
        "    private readonly WebApplicationFactory<Program> _factory;\n\n"
        "    public HealthEndpointTests(WebApplicationFactory<Program> factory)\n"
        "    {\n"
        "        _factory = factory;\n"
        "    }\n\n"
        "    [Fact]\n"
        "    public async Task Health_Returns_Ok()\n"
        "    {\n"
        "        var client = _factory.CreateClient();\n"
        "        var response = await client.GetAsync(\"/health\");\n"
        "        response.StatusCode.Should().Be(HttpStatusCode.OK);\n"
        "    }\n\n"
        "    [Fact]\n"
        "    public async Task HealthReady_Returns_Ok()\n"
        "    {\n"
        "        var client = _factory.CreateClient();\n"
        "        var response = await client.GetAsync(\"/health/ready\");\n"
        "        response.StatusCode.Should().Be(HttpStatusCode.OK);\n"
        "    }\n"
        "}\n"
    )


def _build_global_json() -> str:
    return (
        "{\n"
        "  \"sdk\": {\n"
        "    \"version\": \"8.0.400\",\n"
        "    \"rollForward\": \"latestFeature\"\n"
        "  }\n"
        "}\n"
    )


def _build_readme(title: str, source_brd: str, slug: str, project_name: str, requirements: list[str], enable_observability: bool) -> str:
    highlights = "\n".join(f"- {item}" for item in requirements[:10])
    observability_line = (
        "- Monitoring and observability wiring requested: Yes"
        if enable_observability
        else "- Monitoring and observability wiring requested: No"
    )
    return (
        f"# {title}\n\n"
        f"Generated from BRD `{source_brd}` by the Azure-native factory runner (.NET specialist).\n\n"
        f"## Implementation Language\n\n"
        f"**.NET 8 (ASP.NET Core minimal API, C#)**\n\n"
        f"## What Was Generated\n"
        f"- `docs/architecture-overview.md`\n"
        f"- `docs/governance-model.md`\n"
        f"- `docs/delivery-milestones.md`\n"
        f"- `docs/success-criteria.md`\n"
        f"- `docs/traceability-matrix.md`\n"
        f"- `diagrams/{slug}.md`\n"
        f"- `diagrams/{slug}.drawio`\n"
        f"- `src/{project_name}.csproj`\n"
        f"- `src/Program.cs`\n"
        f"- `src/appsettings.json`\n"
        f"- `src/appsettings.Development.json`\n"
        f"- `src/Dockerfile`\n"
        f"- `src/.dockerignore`\n"
        f"- `tests/{project_name}.Tests.csproj`\n"
        f"- `tests/HealthEndpointTests.cs`\n"
        f"- `global.json`\n\n"
        f"## Selected Generation Options\n{observability_line}\n\n"
        f"## BRD Requirement Highlights\n{highlights}\n"
    )


def _build_deploy(slug: str, project_name: str, enable_observability: bool) -> str:
    deployment_steps = [
        "1. Review and customize the infrastructure templates under `infra/`.",
        "2. Provision hosting (Container Apps), user-assigned managed identity, Key Vault access, and Application Insights.",
        "3. Configure app settings via `ASPNETCORE_*` and `APPLICATIONINSIGHTS_CONNECTION_STRING`; use DefaultAzureCredential for Azure SDK clients.",
        f"4. Build & push the container image: `docker build -t <registry>/{slug}:latest src/ && docker push <registry>/{slug}:latest`.",
        f"5. Deploy the project from `projects/{slug}`.",
        "6. Validate `/health` and `/health/ready` after deployment.",
    ]
    if enable_observability:
        deployment_steps[1] = (
            "2. Provision hosting (Container Apps), user-assigned managed identity, Key Vault access, "
            "Application Insights, and Log Analytics."
        )
        deployment_steps.append(
            "7. Confirm Application Insights is receiving request + dependency telemetry and that alerts fire."
        )
    return (
        "# Deploy\n\n"
        "## Prerequisites\n"
        "- .NET 8 SDK\n"
        "- Docker Desktop (or compatible container runtime)\n"
        "- Azure CLI authenticated\n"
        "- Target Azure subscription and resource group\n\n"
        "## Local Validation\n"
        "```bash\n"
        "cd src\n"
        f"dotnet restore {project_name}.csproj\n"
        f"dotnet build {project_name}.csproj -c Release\n"
        "cd ../tests\n"
        f"dotnet test {project_name}.Tests.csproj -c Release --no-restore\n"
        "```\n\n"
        "## Local Run\n"
        "```bash\n"
        "cd src\n"
        f"dotnet run --project {project_name}.csproj\n"
        "# Service listens on http://localhost:8080 (ASPNETCORE_URLS)\n"
        "# curl http://localhost:8080/health\n"
        "```\n\n"
        "## Azure Deployment Outline\n"
        + "\n".join(deployment_steps)
        + "\n"
    )


# ---------------------------------------------------------------------------
# Archetype: extraction-chat (C# equivalent of the Python extraction-chat
# scaffold -- document upload + extraction + clarification loop + HIL chat)
# ---------------------------------------------------------------------------


_EXTRACTION_MODELS_CS = '''\
namespace GeneratedApi.Models;

public record Clarification(string Field, string Prompt);

public record ExtractionDraft(
    string DocumentId,
    string SourceFilename,
    Dictionary<string, string?> Fields,
    string RawExcerpt
);

public record ExtractionResult(Dictionary<string, string?> Fields, string RawExcerpt);

public record UploadResponse(string DocumentId, List<Clarification> Clarifications, ExtractionDraft Draft);

public record ChatRequest(string? Field, string Answer);

public record ChatResponse(string DocumentId, ExtractionDraft Draft, List<Clarification> Clarifications);

public record ClarificationBundle(string DocumentId, List<Clarification> Clarifications);

public record DraftResponse(string DocumentId, ExtractionDraft Draft, DateTimeOffset FinalizedAt);
'''


_EXTRACTION_INGESTION_CS = '''\
namespace GeneratedApi.Services;

public record IngestedDocument(string Filename, string ContentType, string TextExcerpt, string Notes);

public class DocumentIngestionService
{
    // Swap this stub for Azure AI Document Intelligence / Form Recognizer.
    public IngestedDocument Ingest(string filename, byte[] payload, string notes = "")
    {
        var lowered = filename.ToLowerInvariant();
        string contentType;
        string textExcerpt;
        if (lowered.EndsWith(".pdf"))
        {
            contentType = "application/pdf";
            textExcerpt = $"[pdf: {payload.Length} bytes -- replace ingestion stub with OCR]";
        }
        else if (lowered.EndsWith(".doc") || lowered.EndsWith(".docx"))
        {
            contentType = "application/msword";
            textExcerpt = $"[word doc: {payload.Length} bytes -- replace ingestion stub]";
        }
        else
        {
            contentType = "text/plain";
            var decoded = System.Text.Encoding.UTF8.GetString(payload);
            textExcerpt = decoded.Length > 2000 ? decoded[..2000] : decoded;
        }
        return new IngestedDocument(filename, contentType, textExcerpt, notes);
    }
}
'''


_EXTRACTION_SERVICE_CS = r'''namespace GeneratedApi.Services;

using System.Text.RegularExpressions;
using GeneratedApi.Models;

public class ExtractionService
{
    // Mandatory domain fields the clarification loop expects.
    public static readonly string[] MandatoryFields =
    {
        "reference_id",
        "submission_date",
        "jurisdiction",
        "summary",
    };

    public ExtractionResult Extract(IngestedDocument doc)
    {
        var text = doc.TextExcerpt ?? string.Empty;
        var fields = new Dictionary<string, string?>();

        var ref_ = Regex.Match(text, @"\b(?:ref|reference)\s*[:#]?\s*([A-Z0-9\-]{4,})", RegexOptions.IgnoreCase);
        if (ref_.Success) fields["reference_id"] = ref_.Groups[1].Value;

        var date = Regex.Match(text, @"\b(20\d{2}-\d{2}-\d{2})\b");
        if (date.Success) fields["submission_date"] = date.Groups[1].Value;

        var jur = Regex.Match(text, @"\bjurisdiction\s*[:=]?\s*([A-Za-z ]{2,40})", RegexOptions.IgnoreCase);
        if (jur.Success) fields["jurisdiction"] = jur.Groups[1].Value.Trim();

        if (text.Length > 0) fields["summary"] = text.Length > 200 ? text[..200] : text;

        return new ExtractionResult(fields, text.Length > 500 ? text[..500] : text);
    }
}
'''


_EXTRACTION_CLARIFICATION_CS = '''\
namespace GeneratedApi.Services;

using GeneratedApi.Models;

public class ClarificationService
{
    private static readonly Dictionary<string, string> FieldPrompts = new()
    {
        ["reference_id"] = "What is the reference ID for this submission?",
        ["submission_date"] = "What is the submission date (YYYY-MM-DD)?",
        ["jurisdiction"] = "Which jurisdiction does this arrangement apply to?",
        ["summary"] = "Please provide a short summary of the arrangement.",
    };

    public List<Clarification> ComputeMissingFields(ExtractionDraft draft)
    {
        var missing = new List<Clarification>();
        foreach (var field in ExtractionService.MandatoryFields)
        {
            draft.Fields.TryGetValue(field, out var value);
            if (string.IsNullOrWhiteSpace(value))
            {
                var prompt = FieldPrompts.TryGetValue(field, out var p)
                    ? p
                    : $"Please provide a value for '{field}'.";
                missing.Add(new Clarification(field, prompt));
            }
        }
        return missing;
    }
}
'''


_EXTRACTION_REPOSITORY_CS = '''\
namespace GeneratedApi.Services;

using System.Collections.Concurrent;
using GeneratedApi.Models;

// In-memory repository -- swap for Cosmos DB / Azure SQL in production.
public class DraftRepository
{
    private readonly ConcurrentDictionary<string, ExtractionDraft> _store = new();

    public void Put(ExtractionDraft draft) => _store[draft.DocumentId] = draft;

    public ExtractionDraft? Get(string documentId)
        => _store.TryGetValue(documentId, out var draft) ? draft : null;

    public IReadOnlyList<string> ListIds() => _store.Keys.ToList();
}
'''


_EXTRACTION_SESSION_CS = '''\
namespace GeneratedApi.Services;

using System.Collections.Concurrent;

public record ChatTurn(DateTimeOffset At, string Field, string Answer);

public record Session(string DocumentId, List<ChatTurn> Turns);

public class SessionService
{
    private readonly ConcurrentDictionary<string, Session> _sessions = new();

    public void RecordTurn(string documentId, string field, string answer)
    {
        var session = _sessions.GetOrAdd(documentId, id => new Session(id, new List<ChatTurn>()));
        lock (session.Turns)
        {
            session.Turns.Add(new ChatTurn(DateTimeOffset.UtcNow, field, answer));
        }
    }

    public Session? Get(string documentId)
        => _sessions.TryGetValue(documentId, out var session) ? session : null;
}
'''


_SAMPLE_CORPUS_README = """\
# Sample Corpus

Drop representative documents (PDFs, text transcripts, sample forms) here
and the generated scaffold will exercise the ingestion stub against them.
`manifest.json` is a simple index the test harness can use to discover
sample documents in a deterministic order.
"""

_SAMPLE_CORPUS_MANIFEST = '{\n  "documents": []\n}\n'


def _build_extraction_csproj(enable_observability: bool) -> str:
    # Adds Microsoft.AspNetCore.Http.Features etc. are already in the web SDK.
    observability_pkg = (
        "    <PackageReference Include=\"Microsoft.ApplicationInsights.AspNetCore\" Version=\"2.23.0\" />\n"
        if enable_observability
        else ""
    )
    return (
        "<Project Sdk=\"Microsoft.NET.Sdk.Web\">\n\n"
        "  <PropertyGroup>\n"
        "    <TargetFramework>net8.0</TargetFramework>\n"
        "    <Nullable>enable</Nullable>\n"
        "    <ImplicitUsings>enable</ImplicitUsings>\n"
        "    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>\n"
        "    <InvariantGlobalization>false</InvariantGlobalization>\n"
        "    <RootNamespace>GeneratedApi</RootNamespace>\n"
        "    <AssemblyName>GeneratedApi</AssemblyName>\n"
        "  </PropertyGroup>\n\n"
        "  <ItemGroup>\n"
        "    <PackageReference Include=\"Microsoft.AspNetCore.OpenApi\" Version=\"8.0.10\" />\n"
        "    <PackageReference Include=\"Swashbuckle.AspNetCore\" Version=\"6.8.1\" />\n"
        "    <PackageReference Include=\"Azure.Identity\" Version=\"1.13.1\" />\n"
        "    <PackageReference Include=\"Microsoft.Extensions.Azure\" Version=\"1.7.6\" />\n"
        f"{observability_pkg}"
        "  </ItemGroup>\n\n"
        "</Project>\n"
    )


def _build_extraction_program(title: str, enable_observability: bool) -> str:
    safe_title = title.replace("\"", "'")
    observability_block = (
        "// Application Insights -- reads APPLICATIONINSIGHTS_CONNECTION_STRING from env.\n"
        "builder.Services.AddApplicationInsightsTelemetry();\n"
        if enable_observability
        else ""
    )
    return (
        "using Microsoft.AspNetCore.Mvc;\n"
        "using GeneratedApi.Models;\n"
        "using GeneratedApi.Services;\n\n"
        "var builder = WebApplication.CreateBuilder(args);\n\n"
        "builder.Services.AddEndpointsApiExplorer();\n"
        "builder.Services.AddSwaggerGen();\n"
        "builder.Services.AddProblemDetails();\n"
        f"{observability_block}"
        "\n"
        "// Domain services (in-memory for scaffold; swap for Cosmos / Azure OpenAI in production).\n"
        "builder.Services.AddSingleton<DocumentIngestionService>();\n"
        "builder.Services.AddSingleton<ExtractionService>();\n"
        "builder.Services.AddSingleton<ClarificationService>();\n"
        "builder.Services.AddSingleton<DraftRepository>();\n"
        "builder.Services.AddSingleton<SessionService>();\n\n"
        "// Upload size limit: 10 MB.\n"
        "builder.Services.Configure<Microsoft.AspNetCore.Http.Features.FormOptions>(o =>\n"
        "{\n"
        "    o.MultipartBodyLengthLimit = 10 * 1024 * 1024;\n"
        "});\n\n"
        "var app = builder.Build();\n\n"
        "if (app.Environment.IsDevelopment())\n"
        "{\n"
        "    app.UseSwagger();\n"
        "    app.UseSwaggerUI();\n"
        "}\n\n"
        "app.UseExceptionHandler();\n\n"
        "// Liveness / readiness probes.\n"
        "app.MapGet(\"/health\", () => Results.Ok(new { status = \"ok\", timestamp = DateTimeOffset.UtcNow }));\n"
        "app.MapGet(\"/health/ready\", () => Results.Ok(new { status = \"ready\", timestamp = DateTimeOffset.UtcNow }));\n\n"
        "var allowedExtensions = new HashSet<string> { \".txt\", \".pdf\", \".doc\", \".docx\", \".md\" };\n\n"
        "// Upload a document, extract structured data, return draft + open clarifications.\n"
        "app.MapPost(\"/documents/upload\", async (\n"
        "    [FromForm] IFormFile file,\n"
        "    [FromForm] string? notes,\n"
        "    DocumentIngestionService ingestion,\n"
        "    ExtractionService extraction,\n"
        "    ClarificationService clarifier,\n"
        "    DraftRepository repo) =>\n"
        "{\n"
        "    if (file is null || string.IsNullOrWhiteSpace(file.FileName))\n"
        "        return Results.BadRequest(new { detail = \"filename required\" });\n"
        "    var ext = Path.GetExtension(file.FileName).ToLowerInvariant();\n"
        "    if (!string.IsNullOrEmpty(ext) && !allowedExtensions.Contains(ext))\n"
        "        return Results.StatusCode(415);\n"
        "    using var ms = new MemoryStream();\n"
        "    await file.CopyToAsync(ms);\n"
        "    var payload = ms.ToArray();\n"
        "    var ingested = ingestion.Ingest(file.FileName, payload, notes ?? string.Empty);\n"
        "    var result = extraction.Extract(ingested);\n"
        "    var documentId = Guid.NewGuid().ToString();\n"
        "    var draft = new ExtractionDraft(documentId, file.FileName, result.Fields, result.RawExcerpt);\n"
        "    repo.Put(draft);\n"
        "    var clarifications = clarifier.ComputeMissingFields(draft);\n"
        "    return Results.Ok(new UploadResponse(documentId, clarifications, draft));\n"
        "})\n"
        ".DisableAntiforgery()\n"
        ".WithName(\"UploadDocument\")\n"
        ".WithOpenApi();\n\n"
        "// Human-in-the-loop chat turn: user answers a clarification, we merge into draft.\n"
        "app.MapPost(\"/documents/{documentId}/chat\", (\n"
        "    string documentId,\n"
        "    [FromBody] ChatRequest payload,\n"
        "    ClarificationService clarifier,\n"
        "    DraftRepository repo,\n"
        "    SessionService sessions) =>\n"
        "{\n"
        "    var draft = repo.Get(documentId);\n"
        "    if (draft is null) return Results.NotFound(new { detail = \"document not found\" });\n"
        "    if (!string.IsNullOrEmpty(payload.Field))\n"
        "    {\n"
        "        draft.Fields[payload.Field] = payload.Answer;\n"
        "        repo.Put(draft);\n"
        "    }\n"
        "    var clarifications = clarifier.ComputeMissingFields(draft);\n"
        "    sessions.RecordTurn(documentId, payload.Field ?? \"(free-form)\", payload.Answer);\n"
        "    return Results.Ok(new ChatResponse(documentId, draft, clarifications));\n"
        "})\n"
        ".WithName(\"ChatTurn\")\n"
        ".WithOpenApi();\n\n"
        "// Retrieve current draft.\n"
        "app.MapGet(\"/documents/{documentId}\", (string documentId, DraftRepository repo) =>\n"
        "{\n"
        "    var draft = repo.Get(documentId);\n"
        "    return draft is null ? Results.NotFound() : Results.Ok(draft);\n"
        "})\n"
        ".WithName(\"GetDocument\")\n"
        ".WithOpenApi();\n\n"
        "// Poll open clarifications.\n"
        "app.MapGet(\"/documents/{documentId}/clarifications\", (\n"
        "    string documentId,\n"
        "    ClarificationService clarifier,\n"
        "    DraftRepository repo) =>\n"
        "{\n"
        "    var draft = repo.Get(documentId);\n"
        "    if (draft is null) return Results.NotFound();\n"
        "    return Results.Ok(new ClarificationBundle(documentId, clarifier.ComputeMissingFields(draft)));\n"
        "})\n"
        ".WithName(\"GetClarifications\")\n"
        ".WithOpenApi();\n\n"
        "// Finalize the draft -- 409 while mandatory fields remain.\n"
        "app.MapPost(\"/documents/{documentId}/draft\", (\n"
        "    string documentId,\n"
        "    ClarificationService clarifier,\n"
        "    DraftRepository repo) =>\n"
        "{\n"
        "    var draft = repo.Get(documentId);\n"
        "    if (draft is null) return Results.NotFound();\n"
        "    var open = clarifier.ComputeMissingFields(draft);\n"
        "    if (open.Count > 0)\n"
        "        return Results.Conflict(new { message = \"mandatory fields missing\", clarifications = open });\n"
        "    return Results.Ok(new DraftResponse(documentId, draft, DateTimeOffset.UtcNow));\n"
        "})\n"
        ".WithName(\"FinalizeDraft\")\n"
        ".WithOpenApi();\n\n"
        f"app.Logger.LogInformation(\"Starting generated extraction-chat API: {safe_title}\");\n"
        "app.Run();\n\n"
        "public partial class Program { }\n"
    )


def _build_extraction_test(project_name: str) -> str:
    return (
        "using System.Net;\n"
        "using FluentAssertions;\n"
        "using Microsoft.AspNetCore.Mvc.Testing;\n"
        "using Xunit;\n\n"
        "public class HealthEndpointTests : IClassFixture<WebApplicationFactory<Program>>\n"
        "{\n"
        "    private readonly WebApplicationFactory<Program> _factory;\n\n"
        "    public HealthEndpointTests(WebApplicationFactory<Program> factory) { _factory = factory; }\n\n"
        "    [Fact]\n"
        "    public async Task Health_Returns_Ok()\n"
        "    {\n"
        "        var client = _factory.CreateClient();\n"
        "        var response = await client.GetAsync(\"/health\");\n"
        "        response.StatusCode.Should().Be(HttpStatusCode.OK);\n"
        "    }\n\n"
        "    [Fact]\n"
        "    public async Task HealthReady_Returns_Ok()\n"
        "    {\n"
        "        var client = _factory.CreateClient();\n"
        "        var response = await client.GetAsync(\"/health/ready\");\n"
        "        response.StatusCode.Should().Be(HttpStatusCode.OK);\n"
        "    }\n\n"
        "    [Fact]\n"
        "    public async Task GetUnknownDocument_Returns_NotFound()\n"
        "    {\n"
        "        var client = _factory.CreateClient();\n"
        "        var response = await client.GetAsync(\"/documents/does-not-exist\");\n"
        "        response.StatusCode.Should().Be(HttpStatusCode.NotFound);\n"
        "    }\n"
        "}\n"
    )


def _build_extraction_readme(title: str, source_brd: str, slug: str, project_name: str,
                              requirements: list[str], enable_observability: bool,
                              emitted_files: list[str]) -> str:
    highlights = "\n".join(f"- {item}" for item in requirements[:10])
    observability_line = (
        "- Monitoring and observability wiring requested: Yes"
        if enable_observability
        else "- Monitoring and observability wiring requested: No"
    )
    emitted_block = "\n".join(f"- `{p}`" for p in emitted_files)
    return (
        f"# {title}\n\n"
        f"Generated from BRD `{source_brd}` by the Azure-native factory runner (.NET specialist).\n\n"
        f"## Implementation Language\n\n"
        f"**.NET 8 (ASP.NET Core minimal API, C#)**\n\n"
        f"## Detected Archetype\n\n"
        f"**extraction-chat** -- Document extraction + clarification loop + human-in-the-loop chat\n\n"
        f"## What Was Generated\n"
        f"- `docs/architecture-overview.md`\n"
        f"- `docs/governance-model.md`\n"
        f"- `docs/delivery-milestones.md`\n"
        f"- `docs/success-criteria.md`\n"
        f"- `docs/traceability-matrix.md`\n"
        f"- `docs/detailed-architecture.md`\n"
        f"- `diagrams/{slug}.md`\n"
        f"- `diagrams/{slug}.drawio`\n"
        f"{emitted_block}\n\n"
        f"## Selected Generation Options\n{observability_line}\n\n"
        f"## BRD Requirement Highlights\n{highlights}\n"
    )


def _build_detailed_architecture(title: str, project_name: str) -> str:
    return (
        f"# {title} -- Detailed Architecture (extraction-chat, .NET)\n\n"
        "## Service boundaries\n\n"
        "| Class | Responsibility | Replace with |\n"
        "|---|---|---|\n"
        "| `Services/DocumentIngestionService.cs` | Parse uploaded bytes into a text excerpt. | Azure AI Document Intelligence |\n"
        "| `Services/ExtractionService.cs` | Extract structured fields from the excerpt. | Azure OpenAI / Foundry agent with JSON mode |\n"
        "| `Services/ClarificationService.cs` | Compute the next missing mandatory field. | Keep deterministic; feed prompts into chat UX. |\n"
        "| `Services/DraftRepository.cs` | Persist drafts across chat turns. | Cosmos DB / Azure SQL |\n"
        "| `Services/SessionService.cs` | Track human-in-the-loop conversation history. | Cosmos DB / App Insights custom events |\n\n"
        "## Data flow\n\n"
        "1. `POST /documents/upload` -> `DocumentIngestionService` -> `ExtractionService` -> persist draft + clarifications.\n"
        "2. UI polls `GET /documents/{id}/clarifications` and asks the user the next question.\n"
        "3. Answer posted to `POST /documents/{id}/chat` -> field merged into draft -> clarifications recomputed.\n"
        "4. Once clarifications is empty, `POST /documents/{id}/draft` finalizes the arrangement.\n\n"
        "## Azure mapping (suggested)\n\n"
        "- Container Apps or App Service for the ASP.NET Core process (port 8080; `/health` + `/health/ready`).\n"
        "- Azure Blob Storage for the raw uploads; `DraftRepository` swaps to Cosmos DB / Azure SQL.\n"
        "- Azure OpenAI or Azure AI Foundry Agent Service for extraction + clarification.\n"
        "- `DefaultAzureCredential` + Managed Identity for all Azure SDK clients.\n"
        "- Application Insights + Log Analytics when `enableObservability` is true.\n"
    )


def _build_extraction_deploy(slug: str, project_name: str, enable_observability: bool) -> str:
    steps = [
        "1. Review and customize the infrastructure templates under `infra/`.",
        "2. Provision hosting (Container Apps), user-assigned managed identity, Key Vault access, and Application Insights.",
        "3. Configure app settings via `ASPNETCORE_*` and `APPLICATIONINSIGHTS_CONNECTION_STRING`; use DefaultAzureCredential for Azure SDK clients.",
        f"4. Build & push the container image: `docker build -t <registry>/{slug}:latest src/ && docker push <registry>/{slug}:latest`.",
        f"5. Deploy the project from `projects/{slug}`.",
        "6. Validate `/health` and `/health/ready` after deployment.",
        "7. Smoke-test the extraction flow: `curl -F file=@sample-corpus/sample.txt https://<host>/documents/upload`.",
    ]
    if enable_observability:
        steps[1] = (
            "2. Provision hosting (Container Apps), user-assigned managed identity, Key Vault access, "
            "Application Insights, and Log Analytics."
        )
        steps.append("8. Confirm Application Insights is receiving request + dependency telemetry and that alerts fire.")
    return (
        "# Deploy\n\n"
        "## Prerequisites\n"
        "- .NET 8 SDK\n"
        "- Docker Desktop (or compatible container runtime)\n"
        "- Azure CLI authenticated\n"
        "- Target Azure subscription and resource group\n\n"
        "## Local Validation\n"
        "```bash\n"
        "cd src\n"
        f"dotnet restore {project_name}.csproj\n"
        f"dotnet build {project_name}.csproj -c Release\n"
        "cd ../tests\n"
        f"dotnet test {project_name}.Tests.csproj -c Release --no-restore\n"
        "```\n\n"
        "## Local Run\n"
        "```bash\n"
        "cd src\n"
        f"dotnet run --project {project_name}.csproj\n"
        "# Service listens on http://localhost:8080 (ASPNETCORE_URLS)\n"
        "# curl http://localhost:8080/health\n"
        "```\n\n"
        "## Azure Deployment Outline\n"
        + "\n".join(steps)
        + "\n"
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class DotnetAgent:
    name = "dotnet"
    display_name = ".NET 8 (ASP.NET Core)"

    def emit(self, ctx: LanguageEmitContext) -> LanguageEmitResult:
        project_root = ctx.project_root
        project_name = _dotnet_project_name(ctx.title)
        src_dir = project_root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        ctx.tests_dir.mkdir(parents=True, exist_ok=True)

        archetype = ctx.archetype if ctx.archetype in {"extraction-chat", "api-service"} else "api-service"

        if archetype == "extraction-chat":
            services_dir = src_dir / "Services"
            services_dir.mkdir(parents=True, exist_ok=True)
            _write_text(src_dir / f"{project_name}.csproj", _build_extraction_csproj(ctx.enable_observability))
            _write_text(src_dir / "Program.cs", _build_extraction_program(ctx.title, ctx.enable_observability))
            _write_text(src_dir / "Models.cs", _EXTRACTION_MODELS_CS)
            _write_text(services_dir / "DocumentIngestionService.cs", _EXTRACTION_INGESTION_CS)
            _write_text(services_dir / "ExtractionService.cs", _EXTRACTION_SERVICE_CS)
            _write_text(services_dir / "ClarificationService.cs", _EXTRACTION_CLARIFICATION_CS)
            _write_text(services_dir / "DraftRepository.cs", _EXTRACTION_REPOSITORY_CS)
            _write_text(services_dir / "SessionService.cs", _EXTRACTION_SESSION_CS)
            _write_text(src_dir / "appsettings.json", _build_appsettings())
            _write_text(src_dir / "appsettings.Development.json", _build_appsettings_dev())
            _write_text(src_dir / "Dockerfile", _build_dockerfile(project_name))
            _write_text(src_dir / ".dockerignore", _build_dockerignore())
            _write_text(ctx.tests_dir / f"{project_name}.Tests.csproj", _build_test_csproj(project_name))
            _write_text(ctx.tests_dir / "HealthEndpointTests.cs", _build_extraction_test(project_name))
            _write_text(project_root / "global.json", _build_global_json())

            corpus_dir = project_root / "sample-corpus"
            corpus_dir.mkdir(parents=True, exist_ok=True)
            _write_text(corpus_dir / "README.md", _SAMPLE_CORPUS_README)
            _write_text(corpus_dir / "manifest.json", _SAMPLE_CORPUS_MANIFEST)

            _write_text(
                project_root / "docs" / "detailed-architecture.md",
                _build_detailed_architecture(ctx.title, project_name),
            )

            files_written = [
                f"src/{project_name}.csproj",
                "src/Program.cs",
                "src/Models.cs",
                "src/Services/DocumentIngestionService.cs",
                "src/Services/ExtractionService.cs",
                "src/Services/ClarificationService.cs",
                "src/Services/DraftRepository.cs",
                "src/Services/SessionService.cs",
                "src/appsettings.json",
                "src/appsettings.Development.json",
                "src/Dockerfile",
                "src/.dockerignore",
                f"tests/{project_name}.Tests.csproj",
                "tests/HealthEndpointTests.cs",
                "global.json",
                "sample-corpus/README.md",
                "sample-corpus/manifest.json",
            ]

            _write_text(
                project_root / "README.md",
                _build_extraction_readme(ctx.title, ctx.source_brd, ctx.slug, project_name,
                                         ctx.requirements, ctx.enable_observability, files_written),
            )
            _write_text(
                project_root / "DEPLOY.md",
                _build_extraction_deploy(ctx.slug, project_name, ctx.enable_observability),
            )
            files_written.extend(["README.md", "DEPLOY.md"])

            return LanguageEmitResult(
                files_written=files_written,
                readme_bullets=[
                    f"- .NET 8 ASP.NET Core minimal API with 6 endpoints (upload/chat/get/clarifications/draft + health)",
                    "- 5 domain services: DocumentIngestion, Extraction, Clarification, DraftRepository, SessionService",
                    "- xUnit + FluentAssertions + WebApplicationFactory integration tests",
                    "- Multi-stage Dockerfile (sdk:8.0 -> aspnet:8.0, port 8080)",
                    "- Sample corpus folder and detailed-architecture doc",
                ],
                primary_source_path="src/Program.cs",
            )

        # --- api-service (default, pre-archetype behaviour) ---
        _write_text(src_dir / f"{project_name}.csproj", _build_csproj(ctx.enable_observability))
        _write_text(src_dir / "Program.cs", _build_program(ctx.title, ctx.enable_observability))
        _write_text(src_dir / "appsettings.json", _build_appsettings())
        _write_text(src_dir / "appsettings.Development.json", _build_appsettings_dev())
        _write_text(src_dir / "Dockerfile", _build_dockerfile(project_name))
        _write_text(src_dir / ".dockerignore", _build_dockerignore())
        _write_text(ctx.tests_dir / f"{project_name}.Tests.csproj", _build_test_csproj(project_name))
        _write_text(ctx.tests_dir / "HealthEndpointTests.cs", _build_test_program())
        _write_text(project_root / "global.json", _build_global_json())
        _write_text(
            project_root / "README.md",
            _build_readme(ctx.title, ctx.source_brd, ctx.slug, project_name, ctx.requirements, ctx.enable_observability),
        )
        _write_text(
            project_root / "DEPLOY.md",
            _build_deploy(ctx.slug, project_name, ctx.enable_observability),
        )

        return LanguageEmitResult(
            files_written=[
                f"src/{project_name}.csproj",
                "src/Program.cs",
                "src/appsettings.json",
                "src/appsettings.Development.json",
                "src/Dockerfile",
                "src/.dockerignore",
                f"tests/{project_name}.Tests.csproj",
                "tests/HealthEndpointTests.cs",
                "global.json",
                "README.md",
                "DEPLOY.md",
            ],
            readme_bullets=[
                f"- .NET 8 ASP.NET Core minimal API ({project_name})",
                "- xUnit + FluentAssertions + WebApplicationFactory integration tests",
                "- Multi-stage Dockerfile (sdk:8.0 → aspnet:8.0, port 8080)",
            ],
            primary_source_path="src/Program.cs",
        )


AGENT = DotnetAgent()
