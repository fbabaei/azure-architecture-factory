# Azure AI Agent Foundry

Azure AI Agent Foundry is a VS Code custom-agent zone for AI engineering support. It combines two modes:

- **Learning mode**: guide users through Azure AI learning modules and labs.
- **Application mode**: help application developers discover, configure, and plug reusable AI agents into real application designs.

Application mode can also route early new-application work to architecture, API/integration contract, data/storage, configuration/environment, test/evaluation, and UX/human workflow specialists before implementation starts. It can assess Microsoft Agent Framework as an optional implementation path when a design needs a runnable agent runtime, tool orchestration, stateful workflows, Foundry lifecycle support, evaluation, tracing, debugging, or deployment readiness. For production-facing designs, it routes to shared specialists for security, monitoring, and operations readiness.

Users can also ask companion agents to walk with them through the step-by-step guides. Use Azure AI Learning Orchestrator for learning tracks, Application Planning Companion Agent to manage application steps and handoffs without running commands, and Application Implementation Validation Agent when a bounded step needs file changes, terminal execution, tests, local servers, or validation evidence.

The initial source material is kept under `external/`:

- `external/mslearn-ai-vision` for vision, generative image/video, and content understanding labs.
- `external/Azure-AI-Engineer-Associate-Notes` for broader Azure AI engineering coverage across AI services, vision, NLP, search, documents, and Azure OpenAI.

The `external/` repositories are ignored by git in this project. Re-clone them when setting up a fresh copy of the Foundry.

```powershell
git clone https://github.com/MicrosoftLearning/mslearn-ai-vision.git external/mslearn-ai-vision
git clone https://github.com/kennethleungty/Azure-AI-Engineer-Associate-Notes.git external/Azure-AI-Engineer-Associate-Notes
```

## Main Entry Points

Use these prompts from VS Code chat:

- `/find-ai-agent` - search the catalog by task, technology, or use case.
- `/browse-ai-agent-foundry` - browse learning and application agents.
- `/design-ai-agent-solution` - choose and configure agents for an application design.
- `/design-from-architecture` - convert Markdown architecture notes, diagrams, or architecture exports into an agent-owned design handoff.
- `/implement-from-brd-prd` - convert BRD/PRD requirements into an agent-mapped implementation plan.
- `/learn-ai-capability` - start a guided learning path.

See the [Prompt Files Guide](docs/prompt-files-guide.md) for when to use each prompt, where it routes, and what output to expect.

## Documentation

- [Overview](docs/overview.md) - architecture, agent layers, routing model, and maintenance flow.
- [Quick Start Guide](docs/quick-start.md) - setup, validation, prompt usage, and first test scenarios.
- [Prompt Files Guide](docs/prompt-files-guide.md) - user guide for choosing the right slash-command entry point.
- [Application Implementation Step By Step](docs/application-implementation-step-by-step.md) - application build flow with planning and implementation companion handoffs.
- [Learning Paths Step By Step](docs/learning-paths-step-by-step.md) - guided learning tracks and application follow-ups.
- [AAF Browser](browser/index.html) - local browser/catalog experience for searching and inspecting agents.

## Related Project

- [Azure Architecture Factory](https://github.com/fbabaei_microsoft/azure-architecture-factory) - AI-driven Azure delivery workspace for turning requirements into architecture, code, infrastructure, documentation, and deployment guidance.

## Browser

Open [browser/index.html](browser/index.html) in a browser to use the local Azure AI Agent Foundry catalog UI. It supports search, audience filters, capability filters, BRD/PRD implementation intake, architecture-to-design intake, agent details, configuration contract previews, and links back to the custom agent files.

## Structure

```text
.github/
├── agents/                  # VS Code custom agents and orchestrators
├── prompts/                 # User-facing slash prompts
└── agent-zone/
    ├── ai-agent-index.json  # Machine-readable catalog and routing metadata
    └── catalog.md           # Human-readable catalog
```

## Design Principles

- Keep learning agents tied to source modules and labs.
- Keep application agents reusable and configurable, not lab-step bound.
- Route broad requests through orchestrators.
- Keep specialists focused on one capability or integration concern.
- Include configuration contracts so app developers can plug agents into their own designs.

## Validation

Run this from the project root to validate JSON and frontmatter basics:

```powershell
pwsh -File scripts/validate-agent-zone.ps1
```
