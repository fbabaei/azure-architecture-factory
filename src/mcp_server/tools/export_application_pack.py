"""export_application_pack — create a standalone, shippable app bundle.

This tool enforces the Application Zone separation model:
- AAF is used to create/export applications.
- Exported applications run independently and do not require AAF runtime.

The tool reads an App Pack manifest from
``factory-templates/application-zone/packs/<packId>/<version>/manifest.json``
and exports selected project assets from ``projects/<sourceSlug>/`` into
``outputs/application-zone/<packId>-<version>-<timestamp>/``.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKS_ROOT = _REPO_ROOT / "factory-templates" / "application-zone" / "packs"
_PROJECTS_ROOT = _REPO_ROOT / "projects"
_DEFAULT_EXPORT_ROOT = _REPO_ROOT / "outputs" / "application-zone"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")

_IGNORE_NAMES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    ".azure",
    ".vscode",
    "logs",
}


def _safe_id(value: str, label: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise ValueError(f"{label} is required.")
    if not _ID_RE.fullmatch(candidate):
        raise ValueError(f"Invalid {label}: '{candidate}'")
    return candidate


def _read_json(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
        return doc if isinstance(doc, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _parse_version_tuple(version: str) -> tuple:
    parts = []
    for token in (version or "").split("."):
        try:
            parts.append(int(token))
        except ValueError:
            parts.append(token)
    return tuple(parts)


def _resolve_manifest(pack_id: str, version: str) -> tuple[Path, dict] | tuple[None, None]:
    pack_dir = _PACKS_ROOT / pack_id
    if not pack_dir.exists():
        return None, None

    if version:
        manifest_path = pack_dir / version / "manifest.json"
        doc = _read_json(manifest_path)
        if doc is None:
            return None, None
        return manifest_path, doc

    candidates = []
    for manifest_path in pack_dir.glob("*/manifest.json"):
        doc = _read_json(manifest_path)
        if not doc:
            continue
        doc_version = doc.get("metadata", {}).get("version", "")
        candidates.append((doc_version, manifest_path, doc))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: _parse_version_tuple(item[0]), reverse=True)
    _, path, doc = candidates[0]
    return path, doc


def _safe_inside(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _copy_entry(source_root: Path, target_root: Path, rel_path: str) -> dict[str, Any]:
    src = (source_root / rel_path).resolve()
    if not _safe_inside(source_root, src):
        return {"path": rel_path, "copied": False, "reason": "Path escapes source root"}

    if not src.exists():
        return {"path": rel_path, "copied": False, "reason": "Not found"}

    dest = target_root / rel_path
    dest_parent = dest.parent
    dest_parent.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        shutil.copytree(
            src,
            dest,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*_IGNORE_NAMES),
        )
        return {"path": rel_path, "copied": True, "type": "dir"}

    shutil.copy2(src, dest)
    return {"path": rel_path, "copied": True, "type": "file"}


def export_application_pack(
    pack_id: str,
    version: str = "",
    output_root: str = "",
) -> dict[str, Any]:
    """Export an Application Zone pack as a standalone deployable bundle.

    Parameters
    ----------
    pack_id:
        App pack identifier (for example: ``casewright``).
    version:
        Optional version. When omitted, exports the latest available version.
    output_root:
        Optional absolute output directory. Defaults to
        ``outputs/application-zone`` under the repository.

    Returns
    -------
    dict
        Export status, resolved paths, included items, and generated metadata.
    """
    try:
        pack_id = _safe_id(pack_id, "pack_id")
        version = version.strip()
    except ValueError as exc:
        return {"error": str(exc)}

    manifest_path, manifest = _resolve_manifest(pack_id, version)
    if manifest_path is None or manifest is None:
        if version:
            return {"error": f"App pack not found: {pack_id}@{version}"}
        return {"error": f"No versions found for app pack: {pack_id}"}

    metadata = manifest.get("metadata", {})
    resolved_version = metadata.get("version", version or "unknown")
    packaging = manifest.get("packaging", {})
    source_slug = packaging.get("sourceProjectSlug") or pack_id
    includes = packaging.get("exportIncludes", [])

    if not isinstance(includes, list) or not includes:
        return {"error": "App pack packaging.exportIncludes is required and must be a non-empty array."}

    source_project = _PROJECTS_ROOT / source_slug
    if not source_project.exists():
        return {"error": f"Source project not found: projects/{source_slug}"}

    if output_root:
        export_root = Path(output_root).resolve()
    else:
        export_root = _DEFAULT_EXPORT_ROOT.resolve()
    export_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    bundle_dir = export_root / f"{pack_id}-{resolved_version}-{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copy_results: list[dict[str, Any]] = []
    for rel_path in includes:
        if not isinstance(rel_path, str) or not rel_path.strip():
            continue
        copy_results.append(_copy_entry(source_project, bundle_dir, rel_path.strip()))

    copied_count = sum(1 for result in copy_results if result.get("copied"))

    (bundle_dir / "app-pack-manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    bundle_manifest = {
        "bundleType": "application-zone-export",
        "createdAt": datetime.now().isoformat(),
        "packId": pack_id,
        "version": resolved_version,
        "sourceProjectSlug": source_slug,
        "executionModel": packaging.get("executionModel", "independent"),
        "sourceManifest": str(manifest_path.relative_to(_REPO_ROOT)).replace("\\", "/"),
        "bundlePath": str(bundle_dir),
        "copiedEntries": copy_results,
        "copiedEntryCount": copied_count,
    }
    (bundle_dir / "bundle-manifest.json").write_text(
        json.dumps(bundle_manifest, indent=2),
        encoding="utf-8",
    )

    (bundle_dir / "INDEPENDENCE.md").write_text(
        "\n".join([
            "# Runtime Independence",
            "",
            "This bundle is intended to run independently from Azure Architecture Factory.",
            "AAF is used only to create/export this application package.",
            "",
            "## Included metadata",
            f"- Pack: {pack_id}",
            f"- Version: {resolved_version}",
            f"- Source project: {source_slug}",
            "",
            "## Notes",
            "- No AAF runtime service is required to execute this application.",
            "- Deploy/run this bundle using its own infrastructure and runtime entry points.",
            "",
        ]),
        encoding="utf-8",
    )

    return {
        "status": "exported",
        "packId": pack_id,
        "version": resolved_version,
        "sourceProjectSlug": source_slug,
        "bundlePath": str(bundle_dir),
        "copiedEntryCount": copied_count,
        "entries": copy_results,
    }
