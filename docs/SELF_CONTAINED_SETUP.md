# Self-Contained Setup (No Sibling Repositories Required)

This guide explains how to run `azure-architecture-factory` as a standalone repository.

## Goal

Run core workflows from this repo only:

1. Factory portal (`factory-portal.html`)
2. Local BRD processing (`scripts/local_brd_runner.py`)
3. Project/diagram/docs browsing under `projects/`, `diagrams/`, and `docs/`

## 1. Clone Only This Repository

You do not need:

1. `mcp-environment-orchestrator`
2. `csa-roadmap-template`
3. `copilot-architecture-suite`

## 2. Python Environment

From repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r demo\requirements.txt
pip install -r requirements.txt
```

If `requirements.txt` is not present for your current branch, install only `demo/requirements.txt` for portal usage.

## 3. Start Factory Portal

```powershell
python scripts\start_factory_portal.py
```

Open:

1. `http://localhost:5501/factory-portal.html`
2. `http://localhost:5501/portal`

## 4. MCP Endpoints (Optional)

The local VS Code MCP config is repository-local in `.vscode/mcp.json` and points to localhost endpoints:

1. `http://localhost:8000/mcp` (`factory-mcp-orchestrator`)
2. `http://localhost:8080/mcp` (`draw-io-mcp`)

These are optional for portal operation. If they are not running, core portal pages still work.

## 5. Draw.io Diagram Viewing (Local)

Use one of:

1. VS Code with Draw.io extension
2. draw.io Desktop app
3. diagrams.net web app (open local file from device)

See `docs/VIEW_DETAILED_ARCHITECTURE.md` for step-by-step instructions.

## 6. Self-Contained Behavior Notes

1. `scripts/local_brd_runner.py` is local and does not shell out to sibling repositories.
2. `scripts/_patch_broken_diagrams.py` now patches this repo only by default.
3. To also patch mirror repos intentionally, set:

```powershell
$env:PATCH_DRAWIO_INCLUDE_MIRRORS = "1"
python scripts\_patch_broken_diagrams.py
```

## 7. Quick Health Checks

```powershell
try { (Invoke-WebRequest -UseBasicParsing http://localhost:5501/health -TimeoutSec 3).StatusCode } catch { $_.Exception.Message }
Test-Path .\factory-portal.html
Test-Path .\projects
```

Expected:

1. Health returns `200`
2. `factory-portal.html` exists
3. `projects` exists
