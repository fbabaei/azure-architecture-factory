"""Add MDR feed entry if missing. One-off restorer."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEED = ROOT / "factory-projects.generated.json"
SLUG = "mdr-support-20260416174652"

feed = json.loads(FEED.read_text(encoding="utf-8"))
existing_slugs = {p.get("slug") for p in feed.get("projects", [])}

if SLUG in existing_slugs:
    print(f"{SLUG} already present; nothing to do")
    raise SystemExit(0)

proj_dir = ROOT / "projects" / SLUG
manifest = json.loads((proj_dir / "project-manifest.json").read_text(encoding="utf-8"))

entry = {
    "slug": SLUG,
    "title": manifest.get("title") or "MDR Support",
    "status": "Ready",
    "generatedFrom": "mdr-support.md",
    "generatedAt": manifest.get("created_at"),
    "options": manifest.get("generation_options", {"enableObservability": False, "networkTier": "public"}),
    "links": {
        "readme": f"projects/{SLUG}/README.md",
        "deploy": f"projects/{SLUG}/DEPLOY.md",
        "diagram": f"projects/{SLUG}/diagrams/{SLUG}.drawio",
        "architectureOverview": f"projects/{SLUG}/docs/architecture-overview.md",
        "traceability": f"projects/{SLUG}/docs/traceability-matrix.md",
    },
    "runLog": f"outputs/brd-runs/20260416-174652-{SLUG.rsplit('-', 1)[0]}.log",
}

# Insert at the top so it shows prominently.
feed.setdefault("projects", []).insert(0, entry)
feed["generatedAt"] = manifest.get("created_at", feed.get("generatedAt"))

FEED.write_text(json.dumps(feed, indent=2) + "\n", encoding="utf-8")
print(f"Added {SLUG} to feed (now {len(feed['projects'])} entries)")
