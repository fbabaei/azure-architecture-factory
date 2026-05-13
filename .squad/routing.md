# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| BRD/PRD analysis, architecture design | Danny / fbArchitect | Read BRD/PRD, design Azure architecture, create ADRs, draw.io diagrams |
| Python services, code scaffolding | Rusty | Generate microservice code, API endpoints, shared libraries, models |
| Bicep/Terraform, Azure infra | Livingston | Write Bicep modules, parameter files, deploy infrastructure |
| ACA Express deployment | aca-express-deployer (agent) | HTTP-only workloads, rapid deploy, MCP servers, AI frontends, no-infra deploys |
| Testing & validation | Basher | Unit tests, integration tests, validate generated services |
| CI/CD, pipelines, deployment | Linus | GitHub Actions, deployment pipelines, monitoring setup |
| Code review | Danny | Review PRs, check quality, architectural compliance |
| Scope & priorities | Danny | What to build next, trade-offs, decisions |
| Session logging | Scribe | Automatic — never needs routing |

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Lead |
| `squad:{name}` | Pick up issue and complete the work | Named member |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, the **Lead** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Lead review.

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. The Lead handles all `squad` (base label) triage.

## Work Type → Agent

| Work Type | Primary | Secondary |
|-----------|---------|----------|
| Architecture, orchestration, decisions | Danny | fbArchitect |
| Azure solution design, WAF alignment | fbArchitect | Danny |
| Python services, code generation | Rusty | — |
| Bicep, Azure deployment, IaC | Livingston | — |
| ACA Express deployment (HTTP workloads) | aca-express-deployer (agent) | azure-project-deployer (fallback) |
| Unit tests, integration, validation | Basher | — |
| CI/CD, deploy pipelines, monitoring | Linus | — |

