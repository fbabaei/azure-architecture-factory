# Project Guidelines

## Architecture
- Treat the files in `diagrams/` as the architecture source of truth.
- If `PRD.md` or `BRD.md` describes a capability or component that is absent from or contradicts `diagrams/`, flag the discrepancy in a comment and do not generate code until the diagram is updated. Do not resolve the conflict silently by choosing one source over the other.
- When a `.drawio` file is present but its XML content has not been extracted and provided in context, use the companion `diagrams/*.md` notes as the authoritative description instead.
- Keep implementation modular and microservice-oriented: isolate service entrypoints, service-specific adapters, and shared libraries.
- Separate infrastructure concerns from application concerns. Put Azure deployment artifacts under `infra/` (see **Infrastructure-as-Code Conventions** below for the mandatory structure).

## Azure Delivery
- Map diagram components to concrete Azure resources before writing code.
- Prefer managed identity, Key Vault, least-privilege RBAC, and environment-driven configuration for production paths.
- Document required Azure resources, identities, secrets, and network assumptions in the relevant README or quick-start document.

## Python Conventions
- Each Python service should expose exactly one external-facing entrypoint and own no more than one bounded-context domain. If a service grows beyond ~300 lines of application logic, evaluate splitting it.
- Place reusable models, config loading, telemetry, and resilience helpers in shared modules instead of duplicating logic across services.
- Favor explicit configuration objects and dependency injection over module-level globals.

## .NET Conventions
- Target .NET 8 LTS (`<TargetFramework>net8.0</TargetFramework>`). Pin via `global.json` at the project root.
- Use ASP.NET Core Minimal APIs for service entrypoints (`Program.cs` with `WebApplication.CreateBuilder`).
- Authenticate to Azure with `DefaultAzureCredential` from `Azure.Identity`. Never embed connection strings or keys in source.
- Use `ILogger<T>` for structured logging. `enable_observability` is a boolean environment variable (`ENABLE_OBSERVABILITY`). Read it at startup with `bool.TryParse(Environment.GetEnvironmentVariable("ENABLE_OBSERVABILITY"), out var obs)` and branch on `obs`. When enabled, register `AddApplicationInsightsTelemetry()` and surface the `APPLICATIONINSIGHTS_CONNECTION_STRING` env var to the container.
- Expose `/health` and `/health/ready` on port 8080 (matches the `containerapp-dotnet.bicep` / Terraform compute defaults).

## Infrastructure-as-Code Conventions

Bicep is the default IaC tool. Use Terraform only when explicitly requested or when an existing Terraform root module already owns the target resource. Never introduce both Bicep and Terraform for the same Azure resource or resource group.

### Bicep (default)
- Main template at `infra/main.bicep`; modules under `infra/modules/`; parameters via `*.bicepparam` in `infra/params/`.
- Each module exposes explicit outputs; no implicit cross-module references.
- Use `@description` on every param and `@secure()` on any sensitive param.

### Terraform
- Layout: `providers.tf`, `variables.tf`, `main.tf`, `outputs.tf`, `terraform.tfvars.example` — all under `infra/`.
- Pin provider versions: `required_version = ">= 1.6.0"` and `azurerm = "~> 4.14"`.
- Every `variable` block has a `description` and `type`; sensitive values use `sensitive = true` and are sourced from Key Vault in production.
- Gate deployments with `terraform validate && terraform fmt -check && terraform plan` before `terraform apply`.
- Keep resource naming consistent with the Bicep equivalents so the two paths are swappable.

## Build and Test
- Install demo dependencies from `demo/requirements.txt` when working on the developer portal.
- Run the order-management validation suite with `python -m pytest ./projects/order-management-platform/tests/unit ./projects/order-management-platform/tests/integration -v --tb=short --no-header`. (POSIX-compatible paths work on Windows, macOS, and Linux.)
- Run the storage self-service validation suite with `python -m unittest discover ./projects/storage-self-service-provisioning/tests`.

## Documentation
- Keep the root `README.md` focused on repo orientation.
- Keep `PRD.md` and `BRD.md` as the product and business source documents.
- Update `QUICKSTART.md` when agent entry points or setup steps change.

## Git and PR Conventions
- One focused PR per change. A single PR must not span more than one issue number. If a change requires both application code and its supporting infrastructure, include both in the same PR only when they cannot be merged or tested independently; otherwise split into sequential PRs referencing the same issue.
- Prefer a single `feat(issue-N): <short description>` commit; use `fix(...)`, `chore(...)`, `docs(...)` when more appropriate.
- Branch from `main`: `feature/issue-<N>-<slug>` for issue work, `feature/<slug>` otherwise.
- Create pull requests using the following steps:
  1. Copy `factory-templates/pr/PR_TEMPLATE.md` to `docs/PR_<TOPIC>.md`.
  2. Fill in the **Requirements Coverage** table (one row per acceptance criterion).
  3. Fill in the **Validation** section with actual command output from the relevant test suite.
  4. Run `gh pr create --body-file docs/PR_<TOPIC>.md --title "<type>(issue-N): <description>"`.
  5. Confirm the body contains `Fixes #<N>` before submitting.
- Reference the issue with `Fixes #<N>` so it auto-closes on merge.
- Never use `git push --no-verify`, never `git push --force` on shared branches, never amend an already-pushed commit without explicit user approval.
- When `deploy: true`, honor the orchestrator's Phase 4.5 approval gate — do not skip it to "save a step".

## AAF Orchestration & Workflows
For guidance on Azure Architecture Factory project orchestration, agent roles, quality gates, modernization workflows, and production readiness processes, see [AAF_WORKFLOW_GUIDE.md](../docs/AAF_WORKFLOW_GUIDE.md).

Key topics covered:
- BRD-driven development and architecture generation
- Agent roles and inter-agent handoffs
- Project lifecycle phases (intake, design, implementation, deployment)
- Quality gates and validation checkpoints
- Security, compliance, cost, and observability reviews
- Requirement traceability
- Modernization and migration patterns
