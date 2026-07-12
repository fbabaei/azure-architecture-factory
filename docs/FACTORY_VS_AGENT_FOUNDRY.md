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
