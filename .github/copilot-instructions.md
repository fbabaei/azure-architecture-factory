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

## Build and Test
- Install Python dependencies from `fabric_medallion/requirements.txt`.
- Run the local pipeline with `python .\fabric_medallion\run_pipeline.py --mode sample`.
- Run tests with `python -m unittest discover .\fabric_medallion\tests`.

## Documentation
- Keep the root `README.md` focused on repo orientation.
- Keep `PRD.md` and `BRD.md` as the product and business source documents.
- Update `QUICKSTART.md` when agent entry points or setup steps change.
