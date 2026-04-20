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


def _build_csproj() -> str:
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
        "  </ItemGroup>\n\n"
        "</Project>\n"
    )


def _build_program(title: str) -> str:
    safe_title = title.replace("\"", "'")
    return (
        "using Microsoft.AspNetCore.Mvc;\n\n"
        "var builder = WebApplication.CreateBuilder(args);\n\n"
        "builder.Services.AddEndpointsApiExplorer();\n"
        "builder.Services.AddSwaggerGen();\n"
        "builder.Services.AddProblemDetails();\n\n"
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


class DotnetAgent:
    name = "dotnet"
    display_name = ".NET 8 (ASP.NET Core)"

    def emit(self, ctx: LanguageEmitContext) -> LanguageEmitResult:
        project_root = ctx.project_root
        project_name = _dotnet_project_name(ctx.title)
        src_dir = project_root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        ctx.tests_dir.mkdir(parents=True, exist_ok=True)

        _write_text(src_dir / f"{project_name}.csproj", _build_csproj())
        _write_text(src_dir / "Program.cs", _build_program(ctx.title))
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
        )


AGENT = DotnetAgent()
