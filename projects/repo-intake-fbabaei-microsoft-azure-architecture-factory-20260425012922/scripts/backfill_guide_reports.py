"""Backfill ``docs/guide-report.md`` + feed metadata for every existing project.

Run once after introducing the guide-report feature:

    python scripts/backfill_guide_reports.py

It generates a report for each ``projects/*`` folder that has a
``project-manifest.json`` and patches ``factory-projects.generated.json`` so
the portal can surface the precomputed report without regenerating projects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from .generate_guide_report import generate_guide_report  # type: ignore
except ImportError:  # pragma: no cover - executed as a script
    from generate_guide_report import generate_guide_report  # type: ignore


def _repo_relative(factory_root: Path, target: Path) -> str:
    try:
        return str(target.resolve().relative_to(factory_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(target)


def main(factory_root: Path) -> int:
    projects_dir = factory_root / "projects"
    feed_path = factory_root / "factory-projects.generated.json"
    if not projects_dir.is_dir():
        print(f"projects dir not found: {projects_dir}", file=sys.stderr)
        return 2

    feed: dict = {}
    if feed_path.is_file():
        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"feed JSON parse error: {exc}", file=sys.stderr)
            return 2
    feed_projects = feed.get("projects") or []
    by_slug = {p.get("slug"): p for p in feed_projects if isinstance(p, dict)}

    patched = 0
    skipped = 0
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        manifest_path = project_dir / "project-manifest.json"
        if not manifest_path.is_file():
            skipped += 1
            continue
        try:
            info = generate_guide_report(project_dir)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[skip] {project_dir.name}: {exc}", file=sys.stderr)
            skipped += 1
            continue

        # Patch manifest.
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
        guide_block = {
            "path": _repo_relative(factory_root, Path(info["report_path"])),
            "generated_at": info["generated_at"],
            "severity_counts": info.get("severity_counts", {}),
        }
        manifest["guide_report"] = guide_block
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        # Patch feed record (if present).
        record = by_slug.get(project_dir.name)
        if record is not None:
            record["guideReport"] = guide_block
            links = record.setdefault("links", {})
            links["guideReport"] = guide_block["path"]

        patched += 1
        print(
            f"[ok] {project_dir.name}  "
            f"crit={guide_block['severity_counts'].get('critical', 0)}"
        )

    if feed_path.is_file():
        feed_path.write_text(
            json.dumps(feed, indent=2) + "\n", encoding="utf-8"
        )
    print(f"\nPatched {patched} project(s); skipped {skipped}.")
    return 0


if __name__ == "__main__":
    repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    raise SystemExit(main(repo_root))
