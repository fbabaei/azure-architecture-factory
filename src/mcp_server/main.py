"""AAF MCP Server — Streamable HTTP entry point.

Start-up
--------
The server is launched by the Dockerfile via::

    python -m src.mcp_server.main

or locally via::

    uvicorn src.mcp_server.main:app --host 0.0.0.0 --port 8000

Transport
---------
Streamable HTTP (MCP 2025-03-26 spec), mounted at ``/mcp``.
A plain ``/health`` endpoint satisfies the Dockerfile HEALTHCHECK.

Tools exposed
-------------
invoke_agent            — Run any AAF specialist agent on any repo path.
list_accessible_agents  — Return the registry of supported agent names.
submit_brd              — Submit a BRD/PRD doc, start the orchestrator.
get_project_status      — Poll phase / run status for a project or run ID.
get_project_artifacts   — Retrieve file listing / content from a project.
list_projects           — Browse the factory project catalog.
export_application_pack — Export a standalone app bundle from an App Pack.
generate_application_pack_parameters — Generate profile-specific deploy parameters.
generate_application_pack_deploy_commands — Generate deploy scripts for bundles.
"""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

# ---------------------------------------------------------------------------
# Tool modules
# ---------------------------------------------------------------------------
from src.mcp_server.tools.invoke_agent import (
    invoke_agent as _invoke_agent,
    list_accessible_agents as _list_accessible_agents,
)
from src.mcp_server.tools.submit_brd import submit_brd as _submit_brd
from src.mcp_server.tools.get_project_status import get_project_status as _get_project_status
from src.mcp_server.tools.get_project_artifacts import get_project_artifacts as _get_project_artifacts
from src.mcp_server.tools.list_projects import list_projects as _list_projects
from src.mcp_server.tools.export_application_pack import export_application_pack as _export_application_pack
from src.mcp_server.tools.generate_application_pack_parameters import (
    generate_application_pack_parameters as _generate_application_pack_parameters,
)
from src.mcp_server.tools.generate_application_pack_deploy_commands import (
    generate_application_pack_deploy_commands as _generate_application_pack_deploy_commands,
)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="azure-architecture-factory",
    version="0.1.0",
    instructions=(
        "You have access to the Azure Architecture Factory (AAF) MCP server. "
        "Use invoke_agent to run AAF specialists against any repository, "
        "submit_brd to start a full project-orchestration pipeline from a "
        "requirements document, and the project tools to browse and retrieve "
        "generated artifacts."
    ),
)


# ---------------------------------------------------------------------------
# Tool: invoke_agent
# ---------------------------------------------------------------------------

@mcp.tool()
def invoke_agent(
    agent_name: str,
    target_path: str = "",
    context: str = "",
    model: str = "",
) -> dict:
    """Invoke a named AAF specialist agent against any repository or project directory.

    Supported agents (pass exact name):
      bicep-infrastructure-validator    — Validate & auto-fix Bicep modules.
      terraform-infrastructure-validator — Validate & auto-fix Terraform files.
      security-compliance-auditor       — OWASP / RBAC / secrets audit.
      source-code-maintainer            — Detect & fix arch-code drift.
      project-traceability-advisor      — Requirements ↔ code ↔ test mapping.
      production-environment-advisor    — Surface production readiness gaps.
      project-observability-advisor     — App Insights / Monitor gap analysis.
      repo-change-agent                 — Plan and apply a repo change.

    Args:
        agent_name: One of the supported agent identifiers above.
        target_path: Absolute path to the repo or project directory.
            Defaults to the AAF repo root when omitted.
        context: Optional extra instructions for the agent, e.g.
            "Focus only on the infra/ folder" or "Mode: drift-check".
        model: Optional Copilot model override, e.g. "claude-sonnet-4-5".

    Returns:
        runId, status, agent, targetPath, sessionId, startedAt, logPath, note
    """
    return _invoke_agent(
        agent_name=agent_name,
        target_path=target_path,
        context=context,
        model=model,
    )


# ---------------------------------------------------------------------------
# Tool: list_accessible_agents
# ---------------------------------------------------------------------------

@mcp.tool()
def list_accessible_agents() -> dict:
    """Return the registry of AAF agents that can be invoked via invoke_agent.

    Returns:
        agents: mapping of agent_name → description
    """
    return _list_accessible_agents()


# ---------------------------------------------------------------------------
# Tool: submit_brd
# ---------------------------------------------------------------------------

@mcp.tool()
def submit_brd(
    brd_content: str,
    project_name: str = "",
    deploy: bool = False,
    region: str = "eastus",
    iac_tool: str = "bicep",
) -> dict:
    """Submit a BRD/PRD document and start the AAF project-orchestrator pipeline.

    The factory will generate: architecture diagram, service code scaffolding,
    Bicep or Terraform infrastructure, tests, and documentation.

    Args:
        brd_content: Full text of the BRD or PRD document (Markdown).
        project_name: Optional human-readable project name.
        deploy: When True, the orchestrator continues through Azure deployment.
        region: Target Azure region (default: eastus).
        iac_tool: IaC toolchain — "bicep" or "terraform" (default: bicep).

    Returns:
        runId, status, brdPath, projectName, sessionId, startedAt, note
    """
    return _submit_brd(
        brd_content=brd_content,
        project_name=project_name,
        deploy=deploy,
        region=region,
        iac_tool=iac_tool,
    )


# ---------------------------------------------------------------------------
# Tool: get_project_status
# ---------------------------------------------------------------------------

@mcp.tool()
def get_project_status(
    slug: str = "",
    run_id: str = "",
) -> dict:
    """Return orchestration phase and/or run status for a factory project.

    Args:
        slug: Project slug (folder name under projects/).
            Reads project-manifest.json for phase, coverage, and artifact paths.
        run_id: Copilot runner run ID from a previous invoke_agent or
            submit_brd call.  Returns live run status from metadata.json.

    Returns:
        Merged status object with project and/or run sub-keys.
    """
    return _get_project_status(slug=slug, run_id=run_id)


# ---------------------------------------------------------------------------
# Tool: get_project_artifacts
# ---------------------------------------------------------------------------

@mcp.tool()
def get_project_artifacts(
    slug: str,
    artifact_type: str = "all",
    include_content: bool = False,
    max_files: int = 50,
) -> dict:
    """Retrieve generated artifacts from a factory project.

    Args:
        slug: Project slug (folder name under projects/).
        artifact_type: Filter category — one of: all, code, bicep, terraform,
            diagrams, docs, tests, manifest, logs.  Default: all.
        include_content: When True, reads and returns file content inline
            (capped at 128 KB per file).  Default: False.
        max_files: Maximum files to return (capped at 200).  Default: 50.

    Returns:
        slug, artifactType, fileCount, truncated, files (path, sizeBytes, content?)
    """
    return _get_project_artifacts(
        slug=slug,
        artifact_type=artifact_type,
        include_content=include_content,
        max_files=max_files,
    )


# ---------------------------------------------------------------------------
# Tool: list_projects
# ---------------------------------------------------------------------------

@mcp.tool()
def list_projects(
    search: str = "",
    status_filter: str = "",
    max_results: int = 50,
) -> dict:
    """Browse the Azure Architecture Factory project catalog.

    Args:
        search: Optional case-insensitive filter on project name, slug, or tags.
        status_filter: Optional status to filter by (e.g. "completed").
        max_results: Maximum projects to return (capped at 200).  Default: 50.

    Returns:
        total, returned, projects list with slug, name, phase, status, …
    """
    return _list_projects(search=search, status_filter=status_filter, max_results=max_results)


# ---------------------------------------------------------------------------
# Tool: export_application_pack
# ---------------------------------------------------------------------------

@mcp.tool()
def export_application_pack(
    pack_id: str,
    version: str = "",
    output_root: str = "",
) -> dict:
    """Export an Application Zone pack as a standalone deployable bundle.

    This tool is designed for runtime decoupling: AAF generates and exports
    app bundles, but exported apps execute independently.

    Args:
        pack_id: Application pack ID (for example: "casewright").
        version: Optional explicit version. If omitted, latest is used.
        output_root: Optional absolute export directory. Defaults to
            ``outputs/application-zone`` under the AAF repository.

    Returns:
        status, bundlePath, pack/version metadata, and copied entries.
    """
    return _export_application_pack(
        pack_id=pack_id,
        version=version,
        output_root=output_root,
    )


# ---------------------------------------------------------------------------
# Tool: generate_application_pack_parameters
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_application_pack_parameters(
    pack_id: str,
    version: str = "",
    profile: str = "dev",
    inputs: dict | None = None,
    bundle_path: str = "",
) -> dict:
    """Generate profile-specific deployment parameter artifacts.

    This tool validates App Pack inputs and emits deployment parameter files
    that can be used directly by independently shipped applications.

    Args:
        pack_id: Application pack ID (for example: "casewright").
        version: Optional explicit version. If omitted, latest is used.
        profile: Environment profile, typically dev/test/prod.
        inputs: Input object matching the App Pack contract.
        bundle_path: Optional exported bundle path. When provided, generated
            files are written under ``<bundle_path>/deploy/parameters``.

    Returns:
        status, output directory, and generated file paths.
    """
    return _generate_application_pack_parameters(
        pack_id=pack_id,
        version=version,
        profile=profile,
        inputs=inputs,
        bundle_path=bundle_path,
    )


# ---------------------------------------------------------------------------
# Tool: generate_application_pack_deploy_commands
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_application_pack_deploy_commands(
    bundle_path: str,
    profile: str = "dev",
    deployment_name: str = "aaf-app-pack-deployment",
    location: str = "eastus",
) -> dict:
    """Generate profile-specific deploy scripts in an exported bundle.

    Args:
        bundle_path: Absolute path to an exported app bundle.
        profile: Deployment profile matching generated parameter files.
        deployment_name: Name used for ARM group deployment.
        location: Default Azure region for resource-group creation.

    Returns:
        status and generated script file paths.
    """
    return _generate_application_pack_deploy_commands(
        bundle_path=bundle_path,
        profile=profile,
        deployment_name=deployment_name,
        location=location,
    )


# ---------------------------------------------------------------------------
# Starlette application — mounts MCP + health endpoint
# ---------------------------------------------------------------------------

async def _health(request: Request) -> JSONResponse:  # noqa: ARG001
    return JSONResponse({"status": "ok", "server": "aaf-mcp", "version": "0.1.0"})


# Build the MCP ASGI app using streamable-http transport.
_mcp_app = mcp.streamable_http_app()

app = Starlette(
    routes=[
        Route("/health", _health),
        Mount("/mcp", app=_mcp_app),
    ],
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8000"))
    uvicorn.run(
        "src.mcp_server.main:app",
        host=host,
        port=port,
        log_level="info",
    )
