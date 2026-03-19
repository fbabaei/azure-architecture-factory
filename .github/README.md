# Copilot Customization

This folder contains workspace-level GitHub Copilot customizations for the repository.

## Contents
- `copilot-instructions.md`: project-wide coding and architecture guidance.
- `agents/`: custom agents for architecture-driven implementation and production-environment discovery.

## Intended Workflow
1. Start with a diagram in `diagrams/`.
2. Use `azure-architecture-implementer` to turn the diagram into code and Azure resource decisions.
3. Use `production-environment-advisor` to identify real production prerequisites before deployment.
4. Keep the root `README.md`, `QUICKSTART.md`, `PRD.md`, and `BRD.md` aligned with the resulting implementation.
