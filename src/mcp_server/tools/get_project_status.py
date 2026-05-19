"""get_project_status — poll a project's orchestration phase or a run's status.

Two ways to call:
  1. ``slug``-only  → read the project-manifest.json for phase + coverage info
  2. ``run_id``-only → read the copilot run metadata.json for live status
  3. Both           → return both views merged
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECTS_DIR = _REPO_ROOT / "projects"

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_slug(slug: str) -> str:
    slug = (slug or "").strip()
    if slug and not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"Invalid project slug: '{slug}'")
    return slug


def _safe_run_id(run_id: str, project_root: Path) -> str:
    run_id = (run_id or "").strip()
    if not run_id:
        return run_id
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"Invalid run ID format: '{run_id}'")
    # Prevent path traversal: resolved run dir must sit inside outputs/copilot/
    runs_root = (project_root / "outputs" / "copilot").resolve()
    candidate = (runs_root / run_id).resolve()
    if runs_root not in candidate.parents and candidate != runs_root:
        raise ValueError(f"Run ID '{run_id}' resolves outside the permitted directory.")
    return run_id


def _read_json(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def get_project_status(
    slug: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    """Return orchestration phase and/or run status for a factory project.

    Parameters
    ----------
    slug:
        Project slug (folder name under ``projects/``).  When supplied, the
        tool reads ``project-manifest.json`` and surfaces phase, coverage, and
        key artifact paths.
    run_id:
        Copilot runner run ID from a previous ``invoke_agent`` or
        ``submit_brd`` call.  When supplied, the tool reads the run's
        ``metadata.json`` and returns live status.

    Returns
    -------
    dict
        Merged status object.  Both keys are optional but at least one must
        be supplied.
    """
    slug = (slug or "").strip()
    run_id = (run_id or "").strip()

    if not slug and not run_id:
        return {"error": "Provide at least one of: slug, run_id."}

    result: dict[str, Any] = {}

    # --- Project manifest view ---
    if slug:
        try:
            slug = _safe_slug(slug)
        except ValueError as exc:
            return {"error": str(exc)}

        project_dir = _PROJECTS_DIR / slug
        manifest_path = project_dir / "project-manifest.json"
        if not manifest_path.exists():
            result["project"] = {
                "slug": slug,
                "error": f"No project-manifest.json found at {manifest_path}",
            }
        else:
            manifest = _read_json(manifest_path)
            if manifest is None:
                result["project"] = {"slug": slug, "error": "Failed to parse project-manifest.json"}
            else:
                result["project"] = {
                    "slug": slug,
                    "phase": manifest.get("phase", manifest.get("currentPhase")),
                    "status": manifest.get("status"),
                    "name": manifest.get("name", manifest.get("projectName")),
                    "region": manifest.get("region"),
                    "language": manifest.get("language"),
                    "iacTool": manifest.get("iac_tool", manifest.get("iacTool")),
                    "requirementsCoverage": manifest.get("requirementsCoverage"),
                    "artifacts": manifest.get("artifacts", []),
                    "updatedAt": manifest.get("updatedAt"),
                }

    # --- Run metadata view ---
    if run_id:
        # run_id could belong to the project dir or the repo root
        search_roots = [_PROJECTS_DIR / slug] if slug else []
        search_roots.append(_REPO_ROOT)

        meta: dict | None = None
        run_meta_path: Path | None = None
        for root in search_roots:
            candidate = root / "outputs" / "copilot" / run_id / "metadata.json"
            if candidate.exists():
                meta = _read_json(candidate)
                run_meta_path = candidate
                break

        if meta is None:
            # Broad scan as fallback — find metadata.json matching the run_id
            for candidate in _REPO_ROOT.glob(f"**/outputs/copilot/{run_id}/metadata.json"):
                meta = _read_json(candidate)
                run_meta_path = candidate
                break

        if meta is None:
            result["run"] = {"runId": run_id, "error": "Run not found."}
        else:
            result["run"] = {
                "runId": meta.get("runId", run_id),
                "status": meta.get("status"),
                "agent": meta.get("agent"),
                "projectSlug": meta.get("projectSlug"),
                "startedAt": meta.get("startedAt"),
                "finishedAt": meta.get("finishedAt"),
                "exitCode": meta.get("exitCode"),
                "sessionId": meta.get("sessionId"),
                "logPath": str(run_meta_path.parent / "session.log") if run_meta_path else None,
            }

    return result
