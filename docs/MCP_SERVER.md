# AAF MCP Server

The **Azure Architecture Factory MCP Server** exposes the factory's core capabilities as a set of tools over the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) Streamable HTTP transport. Any MCP-compatible client — GitHub Copilot, Claude Desktop, Cursor, Continue, or your own agent — can invoke AAF specialists, start full orchestration pipelines, and retrieve project artifacts without touching the portal UI or CLI.

---

## Contents

1. [Architecture overview](#architecture-overview)
2. [Quick start](#quick-start)
3. [Tool reference](#tool-reference)
   - [invoke\_agent](#invoke_agent)
   - [list\_accessible\_agents](#list_accessible_agents)
   - [submit\_brd](#submit_brd)
   - [get\_project\_status](#get_project_status)
   - [get\_project\_artifacts](#get_project_artifacts)
   - [list\_projects](#list_projects)
4. [Use-case examples](#use-case-examples)
5. [Security and limits](#security-and-limits)
6. [Configuration reference](#configuration-reference)

---

## Architecture overview

```
MCP client (Copilot / Claude / Cursor / …)
        │  Streamable HTTP  (POST /mcp)
        ▼
┌──────────────────────────────────────────────┐
│  AAF MCP Server  (src/mcp_server/main.py)    │
│  FastMCP · Starlette · Uvicorn · port 8000   │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │  Tools                               │    │
│  │  invoke_agent          list_agents   │    │
│  │  submit_brd            list_projects │    │
│  │  get_project_status                  │    │
│  │  get_project_artifacts               │    │
│  └──────────────────────────────────────┘    │
│          │                                   │
│          ▼                                   │
│  scripts/copilot_runner.py                   │
│  (GitHub Copilot CLI gateway)                │
└──────────────────────────────────────────────┘
        │
        ▼
  .github/agents/*.agent.md  ←  AAF specialist definitions
  projects/<slug>/            ←  generated project output
```

The server runs inside the existing `Dockerfile.mcp-server` container. The `/health` endpoint is used by the container health check; all tool calls go to `/mcp`.

---

## Quick start

### 1 — Run the server locally

```bash
# From the repo root, with the virtual environment active:
pip install -e ".[mcp]"           # or: pip install -r requirements.txt
uvicorn src.mcp_server.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify it is up:

```bash
curl http://localhost:8000/health
# → {"status":"ok","server":"aaf-mcp","version":"0.1.0"}
```

### 2 — Run with Docker

```bash
docker build -f Dockerfile.mcp-server -t aaf-mcp-server .
docker run -p 8000:8000 \
  -e COPILOT_CLI_BIN=/usr/local/bin/gh \
  -v "$HOME/.config/gh:/root/.config/gh:ro" \
  aaf-mcp-server
```

### 3 — Connect a client

#### GitHub Copilot (VS Code `mcp.json`)

```jsonc
// .vscode/mcp.json  (or user-level settings)
{
  "servers": {
    "azure-architecture-factory": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "aaf": {
      "transport": {
        "type": "streamable-http",
        "url": "http://localhost:8000/mcp"
      }
    }
  }
}
```

#### Python client (programmatic)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            "list_accessible_agents", arguments={}
        )
        print(result.content)
```

---

## Tool reference

### `invoke_agent`

Invoke a named AAF specialist agent against any repository or project directory.

**Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_name` | string | yes | Exact name of the agent to run (see [agent registry](#agent-registry)). |
| `target_path` | string | no | Absolute path to the repository or project directory. Defaults to the AAF repo root. |
| `context` | string | no | Extra freeform instructions, e.g. `"Focus only on the infra/ folder"`. |
| `model` | string | no | Copilot model override, e.g. `"claude-sonnet-4-5"`. Omit to use the runner default. |

**Response**

```jsonc
{
  "runId": "abc123",
  "status": "running",
  "agent": "security-compliance-auditor",
  "targetPath": "/repos/my-service",
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "startedAt": "2026-05-18T10:34:00Z",
  "logPath": "/repos/my-service/outputs/copilot/abc123/session.log",
  "note": "Run dispatched. Use get_project_status with runId to poll progress…"
}
```

#### Agent registry

| Agent name | What it does |
|------------|--------------|
| `bicep-infrastructure-validator` | Validate and auto-fix Bicep modules + parameter files. |
| `terraform-infrastructure-validator` | Validate and auto-fix Terraform `.tf` files. |
| `security-compliance-auditor` | OWASP Top 10 / RBAC / secrets audit across services and IaC. |
| `source-code-maintainer` | Detect architecture-code drift and apply targeted fixes. |
| `project-traceability-advisor` | Map requirements → code → tests; compute coverage metrics. |
| `production-environment-advisor` | Surface runtime, identity, network, and ops prerequisites. |
| `project-observability-advisor` | App Insights / Azure Monitor gap analysis + Bicep fixes. |
| `repo-change-agent` | Inspect a repo, plan the minimal change, implement and validate it. |

---

### `list_accessible_agents`

Return the registry of AAF agents that can be called via `invoke_agent`. No parameters.

**Response**

```jsonc
{
  "agents": {
    "bicep-infrastructure-validator": "Validate and auto-fix Bicep modules…",
    "security-compliance-auditor": "Audit services, Bicep/Terraform modules…",
    // …
  }
}
```

---

### `submit_brd`

Submit a BRD/PRD document (Markdown text) and start the full AAF project-orchestrator pipeline.

The tool writes the BRD to `tmp/mcp-brd-<id>.md` and invokes `project-orchestrator` (Phases 1–4, optionally Phase 5 deploy). The generated project lands in `projects/<slug>/`.

**Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `brd_content` | string | yes | Full Markdown text of the BRD or PRD (≤ 200 000 characters). |
| `project_name` | string | no | Human-readable project name. Auto-derived from the BRD title when omitted. |
| `deploy` | boolean | no | When `true`, continue through the Azure deployment phase. Default: `false`. |
| `region` | string | no | Target Azure region. Default: `"eastus"`. |
| `iac_tool` | string | no | `"bicep"` (default) or `"terraform"`. |

**Response**

```jsonc
{
  "runId": "xyz789",
  "status": "running",
  "brdPath": "/workspace/aaf/tmp/mcp-brd-a1b2c3d4.md",
  "projectName": "order-management-platform",
  "sessionId": "…",
  "startedAt": "2026-05-18T10:35:00Z",
  "note": "Orchestration started. Poll with get_project_status(run_id='xyz789')."
}
```

---

### `get_project_status`

Poll the orchestration phase of a project or the live status of a Copilot runner run.

Supply at least one of `slug` or `run_id`. Supplying both returns a merged view.

**Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `slug` | string | no | Project folder name under `projects/`. |
| `run_id` | string | no | Run ID returned by `invoke_agent` or `submit_brd`. |

**Response — slug view**

```jsonc
{
  "project": {
    "slug": "order-management-platform",
    "phase": 4,
    "status": "completed",
    "name": "Order Management Platform",
    "region": "eastus",
    "language": "python",
    "iacTool": "bicep",
    "requirementsCoverage": 94,
    "artifacts": ["diagrams/", "src/", "infra/", "tests/"],
    "updatedAt": "2026-05-18T11:00:00Z"
  }
}
```

**Response — run view**

```jsonc
{
  "run": {
    "runId": "xyz789",
    "status": "running",
    "agent": "project-orchestrator",
    "startedAt": "2026-05-18T10:35:00Z",
    "exitCode": null
  }
}
```

---

### `get_project_artifacts`

Retrieve the file listing (and optionally the content) of artifacts generated for a project.

**Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `slug` | string | yes | Project folder name under `projects/`. |
| `artifact_type` | string | no | Category filter. One of `all`, `code`, `bicep`, `terraform`, `diagrams`, `docs`, `tests`, `manifest`, `logs`. Default: `"all"`. |
| `include_content` | boolean | no | When `true`, return file content inline (≤ 128 KB per file). Default: `false`. |
| `max_files` | integer | no | Maximum files to return (1–200). Default: `50`. |

**Response**

```jsonc
{
  "slug": "order-management-platform",
  "artifactType": "bicep",
  "fileCount": 6,
  "truncated": false,
  "files": [
    { "path": "infra/main.bicep", "sizeBytes": 3412 },
    { "path": "infra/modules/storage.bicep", "sizeBytes": 891 }
  ]
}
```

---

### `list_projects`

Browse the factory project catalog.

**Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | string | no | Case-insensitive filter on name, slug, or tags. |
| `status_filter` | string | no | Exact status match, e.g. `"completed"`, `"in-progress"`, `"failed"`. |
| `max_results` | integer | no | Max projects to return (1–200). Default: `50`. |

**Response**

```jsonc
{
  "total": 12,
  "returned": 12,
  "projects": [
    {
      "slug": "order-management-platform",
      "name": "Order Management Platform",
      "phase": 4,
      "status": "completed",
      "language": "python",
      "iacTool": "bicep",
      "region": "eastus",
      "requirementsCoverage": 94,
      "createdAt": "2026-05-15T09:00:00Z",
      "updatedAt": "2026-05-18T11:00:00Z",
      "tags": ["e-commerce", "python"]
    }
  ]
}
```

---

## Use-case examples

The examples below use the Python MCP client for clarity. The same tool calls work identically from any MCP-compatible interface (Copilot agent mode, Claude Desktop tool panel, etc.).

---

### Use case 1 — Security audit any repository

Run the security-compliance-auditor on an external service before a deployment.

```python
result = await session.call_tool("invoke_agent", arguments={
    "agent_name": "security-compliance-auditor",
    "target_path": "/repos/payment-service",
    "context": "Focus on secrets in source, missing managed identity, and open NSG rules.",
})
run_id = result.content[0].text  # parse JSON → result["runId"]

# Poll until complete
import asyncio, json
while True:
    status = await session.call_tool("get_project_status", arguments={"run_id": run_id})
    data = json.loads(status.content[0].text)
    if data["run"]["status"] not in ("running", "queued"):
        break
    await asyncio.sleep(10)
```

---

### Use case 2 — Validate Bicep infrastructure before a PR merge

Invoke the Bicep validator on a feature branch checkout:

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "bicep-infrastructure-validator",
    "target_path": "/repos/my-platform",
    "context": "Review infra/modules/ only. Report all az-lint and schema errors.",
})
```

For Terraform:

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "terraform-infrastructure-validator",
    "target_path": "/repos/my-platform",
    "context": "Pin azurerm provider versions. Check for hardcoded credentials.",
})
```

---

### Use case 3 — Full project generation from a BRD

Paste requirements inline and let the factory generate architecture, code, and infrastructure end-to-end:

```python
brd = """
# Inventory Sync Service

## Problem
The warehouse system updates stock levels in a legacy Oracle DB. The e-commerce
platform reads stale counts causing overselling.

## Solution
A real-time sync service that listens to Oracle change-data-capture events
(published to an Event Hub), transforms them, and writes to Azure Cosmos DB
so the e-commerce layer always reads current stock.

## Requirements
- REQ-01: Ingest CDC events from Azure Event Hubs (≥ 5 000 msg/s)
- REQ-02: Idempotent upsert to Cosmos DB (SQL API)
- REQ-03: Dead-letter queue for failed messages
- REQ-04: Deployable as an Azure Container App
- REQ-05: Managed Identity — no connection strings in source
- REQ-06: Application Insights telemetry

## Constraints
- Language: Python 3.12
- IaC: Bicep
- Region: West Europe
"""

result = await session.call_tool("submit_brd", arguments={
    "brd_content": brd,
    "project_name": "inventory-sync-service",
    "region": "westeurope",
    "iac_tool": "bicep",
    "deploy": False,
})
run_id = json.loads(result.content[0].text)["runId"]
```

Poll for completion and then fetch the generated Bicep files:

```python
# Wait for orchestration to finish
while True:
    s = json.loads((await session.call_tool(
        "get_project_status", arguments={"run_id": run_id}
    )).content[0].text)
    if s["run"]["status"] not in ("running", "queued"):
        break
    await asyncio.sleep(15)

# Retrieve all Bicep files with content
artifacts = await session.call_tool("get_project_artifacts", arguments={
    "slug": "inventory-sync-service",
    "artifact_type": "bicep",
    "include_content": True,
})
files = json.loads(artifacts.content[0].text)["files"]
for f in files:
    print(f["path"], "—", f["sizeBytes"], "bytes")
    print(f.get("content", ""))
```

---

### Use case 4 — Architecture-code drift detection

Find and fix drift between the `.drawio` diagram and the source code:

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "source-code-maintainer",
    "target_path": "/workspace/aaf/projects/order-management-platform",
    "context": "mode: drift-check. Report service-boundary violations and missing adapters.",
})
```

Apply the fixes automatically (remove `drift-check` to switch to write mode):

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "source-code-maintainer",
    "target_path": "/workspace/aaf/projects/order-management-platform",
    "context": "mode: sync. Apply all drift fixes automatically.",
})
```

---

### Use case 5 — Requirements traceability report

Generate a coverage matrix that links every requirement to the code and tests:

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "project-traceability-advisor",
    "target_path": "/workspace/aaf/projects/order-management-platform",
})

# Retrieve the report once the run finishes
artifacts = await session.call_tool("get_project_artifacts", arguments={
    "slug": "order-management-platform",
    "artifact_type": "docs",
    "include_content": True,
})
docs = json.loads(artifacts.content[0].text)["files"]
report = next((d for d in docs if "traceability" in d["path"].lower()), None)
if report:
    print(report["content"])
```

---

### Use case 6 — Production readiness check

Surface all runtime, identity, networking, and monitoring prerequisites before going live:

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "production-environment-advisor",
    "target_path": "/workspace/aaf/projects/inventory-sync-service",
    "context": "Include ACA-specific prerequisites. Check Managed Identity RBAC assignments.",
})
```

---

### Use case 7 — Observability gap analysis

Check Application Insights and Azure Monitor configuration and get auto-generated Bicep fixes:

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "project-observability-advisor",
    "target_path": "/workspace/aaf/projects/inventory-sync-service",
    "context": "generate-bicep: true. Focus on distributed tracing and missing alert rules.",
})
```

---

### Use case 8 — Browse the project catalog

List all completed projects, then filter by language:

```python
# All completed projects
result = await session.call_tool("list_projects", arguments={
    "status_filter": "completed",
})
projects = json.loads(result.content[0].text)["projects"]

# Only Python projects matching "sync"
result = await session.call_tool("list_projects", arguments={
    "search": "sync",
    "max_results": 10,
})
```

---

### Use case 9 — Apply a targeted repo change

Ask the repo-change-agent to add OpenTelemetry tracing to an existing service:

```python
await session.call_tool("invoke_agent", arguments={
    "agent_name": "repo-change-agent",
    "target_path": "/repos/inventory-sync-service",
    "context": (
        "Goal: add OpenTelemetry SDK tracing to the Event Hub consumer loop. "
        "Export traces to Azure Application Insights. "
        "Write a change summary to docs/CHANGE_OTEL.md."
    ),
})
```

---

### Use case 10 — Discover available agents (dynamic)

Useful for building agent-picker UIs or dynamic tool routing:

```python
result = await session.call_tool("list_accessible_agents", arguments={})
registry = json.loads(result.content[0].text)["agents"]
for name, description in registry.items():
    print(f"{name:45s} {description[:60]}…")
```

---

## Security and limits

| Constraint | Detail |
|------------|--------|
| Agent allowlist | `invoke_agent` only accepts names in the explicit `ACCESSIBLE_AGENTS` registry — arbitrary agent names are rejected with a validation error. |
| Slug / run ID validation | Both inputs are validated with strict regex (`^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$`) before any filesystem access. |
| Path confinement | All artifact reads are resolved and verified to sit inside `projects/<slug>/` before any file is opened. |
| Inline content cap | `get_project_artifacts` with `include_content: true` caps each file at **128 KB** and total results at `max_files` (≤ 200). |
| BRD content cap | `submit_brd` rejects `brd_content` longer than **200 000 characters**. |
| No unauthenticated write paths | The MCP endpoint itself has no mutation surface outside of triggering Copilot CLI runs, which require a valid GitHub Copilot session on the host. |

> **Note on production deployment**: add an authentication layer (e.g. Azure API Management, Entra ID token validation middleware) in front of the `/mcp` endpoint before exposing it outside a trusted network. The server itself does not enforce authentication.

---

## Configuration reference

Environment variables consumed by `src/mcp_server/main.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HOST` | `0.0.0.0` | Bind address for Uvicorn. |
| `MCP_PORT` | `8000` | Bind port for Uvicorn. |
| `COPILOT_CLI_BIN` | *(runner-default)* | Path to the `gh` binary used by `copilot_runner`. |

The server discovers the AAF repo root automatically at import time via `Path(__file__).resolve().parents[3]` — no environment variable is needed as long as `src/mcp_server/` is inside the factory repo tree.
