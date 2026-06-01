"""Opt-out smoke: generateInfra=false + runSecurityAudit=false.

Verifies:
  - infra/ is NOT created
  - manifest.iac_tool == "disabled"
  - manifest.iac_files == []
  - generation_options.generateInfra == False
  - generation_options.runSecurityAudit == False
  - src/ still produced (language emission unaffected)
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from local_brd_runner import process_brd_document  # noqa: E402


BRD = """# Docs-only Spike

## Purpose
Prototype a service entry point without provisioning infra. Not for production.

## Key Requirements
- Expose POST /echo
- Return JSON with the same payload

## Success Criteria
- Handler returns 200 for valid input
"""


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="optout-"))
    brd_path = tmp / "docs-only-spike.md"
    brd_path.write_text(BRD, encoding="utf-8")
    run_id = f"optout-{uuid4().hex[:8]}"

    try:
        result = process_brd_document(
            factory_repo_root=REPO,
            brd_path=brd_path,
            run_id=run_id,
            generation_options={
                "enableObservability": True,
                "generateInfra": False,
                "runSecurityAudit": False,
            },
        )
        slug = result["project"]["slug"]
        proj = REPO / "projects" / slug
        manifest = json.loads((proj / "project-manifest.json").read_text(encoding="utf-8"))

        checks: list[tuple[str, bool, str]] = []
        infra_dir = proj / "infra"
        src_dir = proj / "src"

        checks.append((
            "infra/ directory NOT created",
            not infra_dir.exists(),
            f"infra/ exists at {infra_dir}",
        ))
        checks.append((
            "manifest.iac_tool == disabled",
            manifest.get("iac_tool") == "disabled",
            f"got {manifest.get('iac_tool')!r}",
        ))
        checks.append((
            "manifest.iac_files == []",
            manifest.get("iac_files") == [],
            f"got {manifest.get('iac_files')!r}",
        ))
        checks.append((
            "generation_options.generateInfra == False",
            manifest.get("generation_options", {}).get("generateInfra") is False,
            f"got {manifest.get('generation_options', {}).get('generateInfra')!r}",
        ))
        checks.append((
            "generation_options.runSecurityAudit == False",
            manifest.get("generation_options", {}).get("runSecurityAudit") is False,
            f"got {manifest.get('generation_options', {}).get('runSecurityAudit')!r}",
        ))
        checks.append((
            "src/ still produced (language emission unaffected)",
            src_dir.exists() and any(src_dir.rglob("*.py")),
            "no .py files under src/",
        ))

        print(f"=== Opt-out smoke  slug: {slug} ===")
        fails = 0
        for name, ok, detail in checks:
            flag = "OK  " if ok else "FAIL"
            print(f"  [{flag}] {name}" + (f" -- {detail}" if not ok else ""))
            if not ok:
                fails += 1

        print(f"\n{'PASS' if fails == 0 else 'FAIL'}: {len(checks) - fails}/{len(checks)} checks passed")
        return 0 if fails == 0 else 1
    finally:
        # cleanup project dir + tmp
        slug = None
        try:
            slug = result["project"]["slug"]  # noqa: F821
        except Exception:
            pass
        if slug:
            shutil.rmtree(REPO / "projects" / slug, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
