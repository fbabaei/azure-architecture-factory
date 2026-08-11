# AgentPack schema v0.1

`AgentPack` is the lighter sibling of `AppPack` for AI Apps & Agents as a Service.

Use `AppPack` for full application offerings that include API/runtime, worker, frontend, infrastructure, runtime profiles, SLOs, upgrade strategy, and full operational ownership.

Use `AgentPack` for reusable AI agents or tools that can be plugged into one or more applications. Agent packs still need governance, but the evidence is scoped to the agent contract and execution model.

## Required fields

- `apiVersion`: currently `aaf.applicationzone/v1`
- `kind`: `AgentPack`
- `metadata.agentPackId`
- `metadata.displayName`
- `metadata.version`
- `metadata.parentAppPackId` when the agent is sourced from an existing app pack
- `runtime.executionMode`: `hosted` or `local-tool`
- `contract.tools[]`: callable tools/endpoints exposed by the agent
- `governance.dataBoundary`
- `governance.authModel`
- `governance.requiredEvidence[]`

## Execution modes

| Mode | Use for | Required evidence |
|---|---|---|
| `hosted` | Shared or service-hosted agents callable by multiple apps | health, auth model, data boundary, tool contract, sample invocation |
| `local-tool` | Single-user local MCP/tooling agents | usage docs, personal-tool boundary, explicit non-service classification |

## Promotion rule

Do not promote personal/local-only tools such as git watchers, desktop scripts, or unmanaged MCP demos into the governed service catalog. They can be documented as personal tools, but not certified as AAPAAS service offerings.

## First canonical AgentPack

The first `AgentPack` uses CaseWright as the canonical source:

- `agentPackId`: `case-knowledge-agent`
- `parentAppPackId`: `casewright`
- `executionMode`: `hosted`
- runtime endpoint: `/api/chat/query`

This avoids duplicating or certifying the sibling Case Assistant implementation while still allowing the CaseWright hosted agent to be marketed and supported as a reusable AI agent offering.
