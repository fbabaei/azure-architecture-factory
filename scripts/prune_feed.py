"""Remove feed entries that point to non-existent project folders."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEED = ROOT / "factory-projects.generated.json"

feed = json.loads(FEED.read_text(encoding="utf-8"))
projects = feed.get("projects", [])
before = len(projects)

kept = []
removed = []
for p in projects:
    slug = p.get("slug")
    if not slug:
        continue
    if (ROOT / "projects" / slug).is_dir():
        kept.append(p)
    else:
        removed.append(slug)

feed["projects"] = kept
# preserve JSON style similar to generator: 2-space indent
FEED.write_text(json.dumps(feed, indent=2) + "\n", encoding="utf-8")

print(f"Feed entries: {before} -> {len(kept)} (removed {len(removed)})")
for s in removed:
    print(f"  - {s}")
