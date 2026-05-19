"""invoke_agent — run any AAF agent against an arbitrary repo path.

This is the core accessibility tool: it lets any MCP-compatible client
(Copilot, Claude Desktop, Cursor, etc.) invoke named AAF specialists
against any repository without needing to open the factory portal or
know how the Copilot CLI runner works.

Agents that make the most sense for point-in-time, cross-repo invocation:

  bicep-infrastructure-validator    Validate/fix Bicep modules in any repo
  terraform-infrastructure-validator Validate/fix Terraform .tf files
  security-compliance-auditor       OWASP/RBAC/secret-scanning audit
  source-code-maintainer            Sync code to architecture, detect drift
  project-traceability-advisor      Map requirements → code → tests coverage
  production-environment-advisor    Surface prod readiness gaps
  project-observability-advisor     App Insights / Monitor gaps
  repo-change-agent                 Inspect repo, plan + apply a change
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap: add the repo scripts/ directory to sys.path so we can import
# copilot_runner without requiring an editable install of the whole project.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import copilot_runner  # type: ignore
    _RUNNER_AVAILABLE = True
except ImportError:
    _RUNNER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

#: Canonical agent names that are safe to invoke on external repos.
#: Keys = agent name; values = short description for the tool schema.
ACCESSIBLE_AGENTS: dict[str, str] = {
    "bicep-infrastructure-validator": (
        "Validate and auto-fix Bicep modules and parameter files "
        "for syntax, logic, and Azure Resource Manager schema compliance."
    ),
    "terraform-infrastructure-validator": (
        "Validate and auto-fix HashiCorp Terraform .tf files for syntax, "
        "logic, and Azure provider configuration errors."
    ),
    "security-compliance-auditor": (
        "Audit services, Bicep/Terraform modules, and dependencies for "
        "OWASP Top 10 and Azure security gaps: secrets in source, missing "
        "managed identity, open network rules, missing audit logging."
    ),
    "source-code-maintainer": (
        "Detect drift between the architecture diagram and the codebase, "
        "then apply targeted incremental fixes to bring them back in sync."
    ),
    "project-traceability-advisor": (
        "Assign REQ-IDs, map each requirement to the code and tests that "
        "implement it, compute coverage metrics, and save a traceability report."
    ),
    "production-environment-advisor": (
        "Surface runtime, Azure, networking, identity, secret, build, "
        "deployment, monitoring, and operational prerequisites for production."
    ),
    "project-observability-advisor": (
        "Audit Application Insights, Log Analytics, Azure Monitor alerts, "
        "and distributed tracing; generate Bicep fixes for gaps found."
    ),
    "repo-change-agent": (
        "Inspect an existing repository, decide the minimal change needed, "
        "implement it, run validation, and produce a change summary."
    ),
}

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,119}$")


def _safe_agent_name(name: str) -> str:
    """Raise ValueError if agent_name is not in the allow-list."""
    name = (name or "").strip().lower()
    if name not in ACCESSIBLE_AGENTS:
        allowed = ", ".join(sorted(ACCESSIBLE_AGENTS))
        raise ValueError(
            f"Unknown agent '{name}'. Allowed agents: {allowed}"
        )
    return name


def _safe_path(raw: str) -> Path:
    """Return a resolved, existing directory path.  Raises ValueError on bad input."""
    raw = (raw or "").strip()
    if not raw:
        # Default to the factory repo root itself.
        return _REPO_ROOT
    p = Path(raw).expanduser().resolve()
    if not p.exists():
        raise ValueError(f"Target path does not exist: {p}")
    if not p.is_dir():
        raise ValueError(f"Target path must be a directory, got: {p}")
    return p


def _build_prompt(agent_name: str, target_path: Path, context: str) -> str:
    """Construct the Copilot CLI prompt for the named agent."""
    lines = [
        f"You are the AAF '{agent_name}' specialist.",
        f"Target directory: {target_path}",
    ]
    if context:
        lines.append(f"Additional context from caller: {context.strip()}")
    lines.append(
        "Proceed with your standard workflow for this agent as documented "
        "in your agent instructions. Focus on the target directory above."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public tool function (registered by main.py)
# ---------------------------------------------------------------------------

def invoke_agent(
    agent_name: str,
    target_path: str = "",
    context: str = "",
    model: str = "",
) -> dict[str, Any]:
    """Invoke a named AAF agent against any repository or project directory.

    Parameters
    ----------
    agent_name:
        One of the supported AAF agent identifiers, e.g.
        ``"security-compliance-auditor"`` or ``"bicep-infrastructure-validator"``.
    target_path:
        Absolute or relative path to the repository or project directory the
        agent should operate on.  Defaults to the AAF repo root when omitted.
    context:
        Optional freeform text passed to the agent as extra instructions —
        e.g. ``"Focus only on the infra/ folder"`` or ``"Mode: drift-check"``.
    model:
        Optional Copilot model override, e.g. ``"claude-sonnet-4-5"``.
        Leaves the runner default when omitted.

    Returns
    -------
    dict
        ``{ runId, status, agent, targetPath, sessionId, startedAt, … }``
        on success, or ``{ error: "…" }`` when the runner is unavailable or
        validation fails.
    """
    # Validate inputs.
    try:
        agent = _safe_agent_name(agent_name)
        path = _safe_path(target_path)
    except ValueError as exc:
        return {"error": str(exc)}

    if not _RUNNER_AVAILABLE:
        return {
            "error": (
                "copilot_runner is not available on this host. "
                "Ensure the Copilot CLI is installed and COPILOT_CLI_BIN is set."
            ),
            "agent": agent,
            "targetPath": str(path),
        }

    prompt = _build_prompt(agent, path, context)

    try:
        metadata = copilot_runner.start_run(
            project_root=path,
            prompt=prompt,
            agent=agent,
            model=model or None,
            requested_by="mcp-invoke_agent",
        )
    except copilot_runner.CopilotRunError as exc:
        return {"error": str(exc), "agent": agent, "targetPath": str(path)}

    return {
        "runId": metadata.get("runId"),
        "status": metadata.get("status"),
        "agent": agent,
        "targetPath": str(path),
        "sessionId": metadata.get("sessionId"),
        "startedAt": metadata.get("startedAt"),
        "logPath": str(path / "outputs" / "copilot" / str(metadata.get("runId", "")) / "session.log"),
        "note": (
            "Run dispatched. Use get_project_status with runId to poll progress, "
            "or get_project_artifacts to retrieve output files once complete."
        ),
    }


def list_accessible_agents() -> dict[str, Any]:
    """Return the registry of agents available via invoke_agent.

    Returns
    -------
    dict
        ``{ agents: { name: description, … } }``
    """
    return {"agents": dict(ACCESSIBLE_AGENTS)}
