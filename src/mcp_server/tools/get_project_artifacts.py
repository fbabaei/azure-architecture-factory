"""get_project_artifacts — retrieve generated artifacts from a factory project.

Lets MCP clients pull generated code, diagrams, Bicep/Terraform, test stubs,
and docs into their context without needing filesystem access to the portal host.

Security: all resolved paths are validated to sit inside ``projects/<slug>/``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECTS_DIR = _REPO_ROOT / "projects"

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")

# File size ceiling for inline content delivery (bytes).
_MAX_INLINE_BYTES = 128 * 1024  # 128 KB

# Artifact type → glob patterns relative to the project root.
_ARTIFACT_GLOBS: dict[str, list[str]] = {
    "all": ["**/*"],
    "code": ["src/**/*.py", "src/**/*.cs", "src/**/*.ts", "src/**/*.js"],
    "bicep": ["infra/**/*.bicep", "infra/**/*.bicepparam"],
    "terraform": ["infra/**/*.tf", "infra/**/*.tfvars*"],
    "diagrams": ["diagrams/**/*.drawio", "diagrams/**/*.md"],
    "docs": ["docs/**/*.md", "*.md"],
    "tests": ["tests/**/*", "*/tests/**/*"],
    "manifest": ["project-manifest.json"],
    "logs": ["logs/**/*.log", "logs/**/*.json"],
}


def _safe_slug(slug: str) -> str:
    slug = (slug or "").strip()
    if not slug:
        raise ValueError("Project slug is required.")
    if not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"Invalid project slug: '{slug}'")
    return slug


def _safe_rel(project_dir: Path, candidate: Path) -> bool:
    """Return True when ``candidate`` is inside ``project_dir``."""
    try:
        candidate.resolve().relative_to(project_dir.resolve())
        return True
    except ValueError:
        return False


def get_project_artifacts(
    slug: str,
    artifact_type: str = "all",
    include_content: bool = False,
    max_files: int = 50,
) -> dict[str, Any]:
    """Retrieve a listing (and optionally the content) of project artifacts.

    Parameters
    ----------
    slug:
        Project slug (folder name under ``projects/``).
    artifact_type:
        Filter to a category.  One of: ``all``, ``code``, ``bicep``,
        ``terraform``, ``diagrams``, ``docs``, ``tests``, ``manifest``,
        ``logs``.  Defaults to ``"all"``.
    include_content:
        When ``True``, the tool reads and returns the file content inline
        (capped at 128 KB per file and ``max_files`` total files).  When
        ``False`` (default), only file paths and sizes are returned.
    max_files:
        Maximum number of files to return.  Capped at 200.

    Returns
    -------
    dict
        ``{ slug, artifactType, files: [{ path, sizeBytes, content? }, …] }``
    """
    try:
        slug = _safe_slug(slug)
    except ValueError as exc:
        return {"error": str(exc)}

    artifact_type = (artifact_type or "all").strip().lower()
    if artifact_type not in _ARTIFACT_GLOBS:
        return {
            "error": (
                f"Unknown artifact_type '{artifact_type}'. "
                f"Valid values: {', '.join(sorted(_ARTIFACT_GLOBS))}."
            )
        }

    max_files = min(max(1, int(max_files)), 200)

    project_dir = _PROJECTS_DIR / slug
    if not project_dir.exists():
        return {"error": f"Project '{slug}' not found under projects/."}

    globs = _ARTIFACT_GLOBS[artifact_type]
    seen: set[Path] = set()
    file_entries: list[dict[str, Any]] = []

    for pattern in globs:
        for candidate in sorted(project_dir.glob(pattern)):
            if not candidate.is_file():
                continue
            if candidate in seen:
                continue
            if not _safe_rel(project_dir, candidate):
                continue
            seen.add(candidate)
            rel = candidate.relative_to(project_dir)
            entry: dict[str, Any] = {
                "path": str(rel).replace("\\", "/"),
                "sizeBytes": candidate.stat().st_size,
            }
            if include_content:
                size = candidate.stat().st_size
                if size <= _MAX_INLINE_BYTES:
                    try:
                        entry["content"] = candidate.read_text(encoding="utf-8", errors="replace")
                    except OSError as exc:
                        entry["contentError"] = str(exc)
                else:
                    entry["contentSkipped"] = f"File too large ({size} bytes > {_MAX_INLINE_BYTES} limit)."
            file_entries.append(entry)
            if len(file_entries) >= max_files:
                break
        if len(file_entries) >= max_files:
            break

    return {
        "slug": slug,
        "artifactType": artifact_type,
        "fileCount": len(file_entries),
        "truncated": len(file_entries) >= max_files,
        "files": file_entries,
    }
