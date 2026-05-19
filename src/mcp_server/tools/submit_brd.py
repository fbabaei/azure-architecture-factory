"""submit_brd — submit requirements text and start the factory pipeline.

Wraps the factory's BRD intake pathway so that any MCP client can kick off a
full project-orchestrator run by supplying a BRD/PRD document inline, without
needing access to the portal UI.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import copilot_runner  # type: ignore
    _RUNNER_AVAILABLE = True
except ImportError:
    _RUNNER_AVAILABLE = False


def submit_brd(
    brd_content: str,
    project_name: str = "",
    deploy: bool = False,
    region: str = "eastus",
    iac_tool: str = "bicep",
) -> dict[str, Any]:
    """Submit a BRD/PRD document and start the AAF project-orchestrator pipeline.

    The tool writes the BRD content to a temporary file under ``tmp/`` and then
    invokes the ``project-orchestrator`` agent with the appropriate arguments.

    Parameters
    ----------
    brd_content:
        Full text of the BRD or PRD document (Markdown supported).
    project_name:
        Optional human-readable name; auto-derived from BRD title when omitted.
    deploy:
        When ``True``, the orchestrator will proceed through the Azure deployment
        phase (Phase 5) after generating infrastructure.
    region:
        Target Azure region for infrastructure generation.  Defaults to
        ``"eastus"``.
    iac_tool:
        Infrastructure-as-code toolchain.  One of ``"bicep"`` or
        ``"terraform"``.  Defaults to ``"bicep"``.

    Returns
    -------
    dict
        ``{ runId, status, brdPath, projectName, … }`` on success,
        or ``{ error: "…" }`` on failure.
    """
    brd_content = (brd_content or "").strip()
    if not brd_content:
        return {"error": "brd_content is required."}

    if len(brd_content) > 200_000:
        return {"error": "brd_content exceeds 200 000 character limit."}

    iac_tool = (iac_tool or "bicep").strip().lower()
    if iac_tool not in {"bicep", "terraform"}:
        return {"error": "iac_tool must be 'bicep' or 'terraform'."}

    # Write BRD to a deterministic temp path inside the repo so the agent can
    # reference it by file path.
    tmp_dir = _REPO_ROOT / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    brd_filename = f"mcp-brd-{uuid.uuid4().hex[:8]}.md"
    brd_path = tmp_dir / brd_filename
    brd_path.write_text(brd_content, encoding="utf-8")

    # Build orchestrator prompt.
    name_hint = f"project_name: {project_name}\n" if project_name else ""
    prompt_lines = [
        "You are the AAF project-orchestrator.",
        f"BRD file path: {brd_path}",
        f"{name_hint}region: {region}",
        f"iac_tool: {iac_tool}",
        f"deploy: {'true' if deploy else 'false'}",
        "Proceed with the full orchestration pipeline (Phases 1–4). "
        "Do NOT skip any phase. Report progress in each phase header.",
    ]
    prompt = "\n".join(prompt_lines)

    if not _RUNNER_AVAILABLE:
        return {
            "error": "copilot_runner is not available on this host.",
            "brdPath": str(brd_path),
        }

    try:
        metadata = copilot_runner.start_run(
            project_root=_REPO_ROOT,
            prompt=prompt,
            agent="project-orchestrator",
            requested_by="mcp-submit_brd",
        )
    except copilot_runner.CopilotRunError as exc:
        return {"error": str(exc), "brdPath": str(brd_path)}

    return {
        "runId": metadata.get("runId"),
        "status": metadata.get("status"),
        "brdPath": str(brd_path),
        "projectName": project_name or "(auto-derived by orchestrator)",
        "sessionId": metadata.get("sessionId"),
        "startedAt": metadata.get("startedAt"),
        "note": (
            "Orchestration run started. Use get_project_status with the runId "
            "or poll the projects/ folder for a new project-manifest.json once "
            "the run completes."
        ),
    }
