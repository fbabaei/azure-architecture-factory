# Azure Architecture Factory

Azure Architecture Factory is an AI-driven Azure delivery workspace that turns requirements into architecture, code, infrastructure, documentation, and deployment guidance. Generated services ship in **Python 3.11 / FastAPI** or **.NET 8 / ASP.NET Core**, with infrastructure in **Bicep** or **Terraform** — selectable per BRD.

## New here? Read these in order

1. [docs/QUICKSTART.md](docs/QUICKSTART.md) — the one-page "how do I use this" guide. Start here.
2. [docs/WORKFLOW_GUIDE.md](docs/WORKFLOW_GUIDE.md) — what each agent does and when to pick one.
3. [docs/BRD_CLASSIFICATION_FLOW.md](docs/BRD_CLASSIFICATION_FLOW.md) — how the factory decides whether a BRD needs the Agent Framework SDK runtime.
4. [docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md](docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md) — when a generated project should ship the Agent Framework SDK runtime vs. stay deterministic.
5. [docs/SELF_CONTAINED_SETUP.md](docs/SELF_CONTAINED_SETUP.md) — running the repo without any sibling checkouts.

Reference material:

- [docs/README.md](docs/README.md) repository overview
- [docs/VIEW_DETAILED_ARCHITECTURE.md](docs/VIEW_DETAILED_ARCHITECTURE.md) viewing `.drawio` files on Windows
- [docs/MDR_PY_VS_DOTNET.md](docs/MDR_PY_VS_DOTNET.md) side-by-side comparison of Python vs .NET output for the same `extraction-chat` BRD
- [docs/PRD.md](docs/PRD.md) product scope and capabilities
- [docs/BRD.md](docs/BRD.md) business case and adoption goals

Key repository areas:

- [.github/agents/README.md](.github/agents/README.md) for the custom Copilot agents
- [diagrams](diagrams) for reusable architecture source artifacts
- [projects](projects) for sample project outputs and generated examples
- [infra/README.md](infra/README.md) for shared Bicep modules and deployment guidance
- [factory-templates/agent-framework/README.md](factory-templates/agent-framework/README.md) for the reusable Microsoft Agent Framework SDK runtime template
- [demo](demo) for the developer-facing portal and readiness dashboard

Current sample portfolio includes order management, storage self-service, AKS microservices, e-commerce, and the restored Fabric Medallion pipeline reference.

If you are evaluating whether the repository is ready for broader internal use, use [docs/README.md](docs/README.md) as the canonical overview and [demo/app.py](demo/app.py) for the developer portal entrypoint.
