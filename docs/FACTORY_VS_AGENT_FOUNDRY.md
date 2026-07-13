# Azure Architecture Factory vs. Azure AI Agent Foundry

A quick orientation to two complementary tools and when to use each.

## TL;DR

- **Azure Architecture Factory** builds and ships the **whole Azure solution** — it turns a BRD/PRD (or a legacy app) into architecture, code, Bicep infrastructure, deployment, and observability.
- **Azure AI Agent Foundry** supplies the **AI building blocks** — search, RAG, vision, NLP, Document Intelligence, and Responsible AI — that you plug into that solution.
- Use the **Factory** to *create and deploy* the app; use the **Foundry** (and the **Reconfigurable Agents** catalog) to *add intelligence* inside it.

## Azure Architecture Factory

**Purpose:** An end-to-end delivery pipeline that turns **business requirements into a running Azure solution**.

**Flow:** Business Requirements → Architecture Design → Implementation (code) → Bicep Infrastructure → Testing → Deployment → Observability (with traceability across every stage).

**Use it when you want to:**

- Submit a **BRD/PRD** and have a full architecture project generated (Azure diagram, scaffolded microservice code, parameterized Bicep, deployment guides).
- **Modernize a legacy app** — point it at an existing codebase; it assesses the stack, maps components to Azure services, generates a BRD, and runs the full pipeline.
- Get **deploy-ready infrastructure** (`azd up` / Bicep CLI), a production-readiness review, cost estimation, and observability wiring.
- Manage generated **projects** and per-project operations (explore, deploy, analyze, estimate cost).

**Primary audience:** Cloud/solution architects and platform engineers standing up whole workloads.

## Azure AI Agent Foundry

**Purpose:** A **discovery and composition layer for AI capabilities** — a catalog of reusable Azure AI agents, learning orchestrators, and application blueprints.

**Use it when you want to:**

- **Find/route** to the right agent for an AI task (search, vision, NLP, Document Intelligence, RAG, Responsible AI).
- Build an **AI feature** from blueprints (RAG search, agentic retrieval, document extraction, vision chat, and more).
- Use **Reconfigurable Agents** — prebuilt AI baselines (Classic/RAG/Agentic Search, Document Intelligence, multimodal, speech, guardrails, evaluation) that you tune to your scenario.
- **Learn** an Azure AI capability through guided learning paths.

**Primary audience:** AI engineers/developers adding intelligent capabilities to an app.

## Side-by-side

| | Azure Architecture Factory | Azure AI Agent Foundry |
|---|---|---|
| **Scope** | Whole cloud workload, requirements → production | AI capabilities within an app |
| **Input** | BRD/PRD, or a legacy codebase | An AI task, scenario, or learning goal |
| **Output** | Diagram + code + Bicep + deployment | Selected/configured AI agent or blueprint |
| **Core concern** | Architecture, infrastructure, delivery, operations | Intelligence: search, RAG, vision, NLP, documents |
| **Analogy** | The *general contractor* building the house | The *smart-home kit* you install inside it |

## How they work together

They are **complementary**, not competing:

1. The **Factory** designs, builds, and deploys the end-to-end Azure solution.
2. The **Foundry** provides the AI building blocks that go inside that solution.

That's why the Factory portal embeds the Foundry directly — via the **AI Agent Foundry** and **Reconfigurable Agents** tabs. When a generated app needs search, RAG, or document intelligence, you pull those agents in without leaving the Factory.

**Typical combined flow:**

1. Start in the Factory: submit a BRD (or modernize a legacy app) → get architecture, code, and infrastructure.
2. Where the app needs intelligence, open the **AI Agent Foundry** tab and pick a blueprint, or open **Reconfigurable Agents** and configure a prebuilt baseline (e.g., RAG search over your documents).
3. Plug the configured agent into the generated app, then let the Factory handle deployment and observability.

## Analyze with AI Agent Foundry (in the BRD intake)

The **Create & Modernize Apps** tab has an **Analyze with AI Agent Foundry** action that maps your Business Requirements to the reusable Azure AI agents the app is likely to need — *before* you build. There are two entry points to the same analysis:

- **Header pill** — "🧭 Analyze with AI Foundry", next to *Draft with BRD Copilot* in the "Submit Business Requirements" header (visible even while the form is collapsed). Clicking it expands the form; if you've already entered requirements it runs the analysis, otherwise it drops you into the requirements box.
- **In-form button** — under the "Architecture Source or Summary" textarea, with the nudge *"Not sure which AI capabilities you need? Analyze your requirements first."*

**What the analysis does:** it sends your requirements to the portal's `/api/agent-foundry/recommend` endpoint (a deterministic keyword scorer — no LLM call), and returns:

- the **best-fit** reusable agent and a **confidence** level,
- a **ranked list** of candidate agents with match scores,
- a short **rationale**.

You can then click **Insert recommendations into BRD** to append a `## Recommended Azure AI Agents (via AI Agent Foundry)` section to your requirements, so the generated project carries that guidance. If the backend is unreachable (e.g., the page is opened as a local file), it falls back to copying a ready-to-run `/implement-from-brd-prd` prompt and offers to open the AI Agent Foundry tab.

### Two ways to run it

**Manual (review-first):**

1. Enter your requirements.
2. Click **Analyze with AI Agent Foundry** → review the ranked recommendations.
3. (Optional) **Insert recommendations into BRD**.
4. Click **🚀 Generate or Update Project**.

**One-click (auto-analyze on Generate)** — controlled by the checkbox **"Automatically include AI Agent Foundry recommendations when I generate the project"** (default **on**), located under the Analyze button:

1. Enter your requirements.
2. Click **🚀 Generate or Update Project**.
3. The portal first consults AI Agent Foundry, **auto-inserts** the recommendations into the BRD, then continues into generation — one click. (The Generate button briefly shows *"Consulting AI Agent Foundry…"*.)

Notes:

- **Analyze and Generate are separate by default.** Analyze is an advisory "which AI agents do I need?" step; it does **not** trigger a build on its own. The auto-analyze checkbox is what chains them.
- **Opt-out:** uncheck the box to generate without the analysis.
- **No double-insert:** if the recommendations section is already present, it won't be added again.
- **Best-effort:** if the analysis call fails, generation proceeds anyway — it never blocks your build.
