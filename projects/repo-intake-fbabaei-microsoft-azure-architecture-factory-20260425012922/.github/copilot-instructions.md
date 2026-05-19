# Project Guidelines

## Architecture
- Treat the files in `diagrams/` as the architecture source of truth.
- Prefer the companion diagram notes (`diagrams/*.md`) when a `.drawio` file is not directly machine-readable.
- Keep implementation modular and microservice-oriented: isolate service entrypoints, service-specific adapters, and shared libraries.
- Separate infrastructure concerns from application concerns. Put Azure deployment artifacts under `infra/` or a service-local `infra/` folder when that structure is introduced.

## Azure Delivery
- Map diagram components to concrete Azure resources before writing code.
- Prefer managed identity, Key Vault, least-privilege RBAC, and environment-driven configuration for production paths.
- Document required Azure resources, identities, secrets, and network assumptions in the relevant README or quick-start document.

## Python Conventions
- Keep Python services small and single-purpose.
- Place reusable models, config loading, telemetry, and resilience helpers in shared modules instead of duplicating logic across services.
- Favor explicit configuration objects and dependency injection over module-level globals.

## .NET Conventions
- Target .NET 8 LTS (`<TargetFramework>net8.0</TargetFramework>`). Pin via `global.json` at the project root.
- Use ASP.NET Core Minimal APIs for service entrypoints (`Program.cs` with `WebApplication.CreateBuilder`).
- Authenticate to Azure with `DefaultAzureCredential` from `Azure.Identity`. Never embed connection strings or keys in source.
- Use `ILogger<T>` for structured logging. When `enable_observability` is on, register `AddApplicationInsightsTelemetry()` and surface the `APPLICATIONINSIGHTS_CONNECTION_STRING` env var to the container.
- Expose `/health` and `/health/ready` on port 8080 (matches the `containerapp-dotnet.bicep` / Terraform compute defaults).

## Infrastructure-as-Code Conventions

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
- Run the order-management validation suite with `python -m pytest .\projects\order-management-platform\tests\unit .\projects\order-management-platform\tests\integration -v --tb=short --no-header`.
- Run the storage self-service validation suite with `python -m unittest discover .\projects\storage-self-service-provisioning\tests`.

## Documentation
- Keep the root `README.md` focused on repo orientation.
- Keep `PRD.md` and `BRD.md` as the product and business source documents.
- Update `QUICKSTART.md` when agent entry points or setup steps change.
