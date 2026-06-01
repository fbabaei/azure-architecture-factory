"""list_projects — browse the factory project catalog.

Scans the ``projects/`` directory for ``project-manifest.json`` files and
returns a summary of each project: name, phase, status, language, IaC tool,
and artifact counts.  Supports optional text search to filter by name or tags.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECTS_DIR = _REPO_ROOT / "projects"


def _read_manifest(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _summarize(slug: str, manifest: dict) -> dict[str, Any]:
    """Extract a concise project summary from its manifest."""
    return {
        "slug": slug,
        "name": manifest.get("name") or manifest.get("projectName") or slug,
        "phase": manifest.get("phase") or manifest.get("currentPhase"),
        "status": manifest.get("status"),
        "language": manifest.get("language"),
        "iacTool": manifest.get("iac_tool") or manifest.get("iacTool"),
        "region": manifest.get("region"),
        "requirementsCoverage": manifest.get("requirementsCoverage"),
        "createdAt": manifest.get("createdAt"),
        "updatedAt": manifest.get("updatedAt"),
        "tags": manifest.get("tags") or [],
    }


def list_projects(
    search: str = "",
    status_filter: str = "",
    max_results: int = 50,
) -> dict[str, Any]:
    """List factory projects from the ``projects/`` directory.

    Parameters
    ----------
    search:
        Optional case-insensitive text to filter project names, slugs, or tags.
    status_filter:
        Optional status string to filter by (e.g. ``"completed"``,
        ``"in-progress"``, ``"failed"``).
    max_results:
        Maximum number of projects to return.  Capped at 200.

    Returns
    -------
    dict
        ``{ total, returned, projects: [ { slug, name, phase, status, … } ] }``
    """
    max_results = min(max(1, int(max_results)), 200)

    if not _PROJECTS_DIR.exists():
        return {"total": 0, "returned": 0, "projects": []}

    search = (search or "").strip().lower()
    status_filter = (status_filter or "").strip().lower()

    summaries: list[dict[str, Any]] = []

    for manifest_path in sorted(_PROJECTS_DIR.glob("*/project-manifest.json")):
        slug = manifest_path.parent.name
        manifest = _read_manifest(manifest_path)
        if manifest is None:
            # Still include stub entry so the caller knows the project exists.
            summaries.append({"slug": slug, "error": "Unreadable manifest"})
            continue

        summary = _summarize(slug, manifest)

        # Apply filters.
        if search:
            searchable = " ".join(
                filter(None, [summary["slug"], summary["name"], " ".join(summary.get("tags") or [])])
            ).lower()
            if search not in searchable:
                continue
        if status_filter and (summary.get("status") or "").lower() != status_filter:
            continue

        summaries.append(summary)

    total = len(summaries)
    returned = min(total, max_results)

    return {
        "total": total,
        "returned": returned,
        "projects": summaries[:max_results],
    }
