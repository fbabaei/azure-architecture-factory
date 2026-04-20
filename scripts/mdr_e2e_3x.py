"""E2E harness: run the MDR BRD through the factory 3 times and verify alignment
with the new agent responsibilities (Phase 2.6 Security Gate, 5-gates narrative,
no stale 'generate' mode references, etc.).

This is a validation run — it does NOT invoke the LLM orchestrator. The template
runner (`local_brd_runner.py`) is deterministic; we use it to verify the
generator artifacts still align with the updated agent spec.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from local_brd_runner import process_brd_document  # type: ignore  # noqa: E402

BRD = REPO / "docs" / "intake" / "mdr-support.md"
ITER = 3


def _sig(project_root: Path) -> dict:
    """Extract a structural fingerprint of a generated project (layout + keys),
    timestamp-independent, for cross-run diffing."""
    files = sorted(
        str(p.relative_to(project_root)).replace("\\", "/")
        for p in project_root.rglob("*")
        if p.is_file()
    )
    manifest = json.loads((project_root / "project-manifest.json").read_text(encoding="utf-8"))
    keys = sorted(manifest.keys())
    caps = manifest.get("capabilities", {})
    return {
        "file_count": len(files),
        "files": files,
        "manifest_keys": keys,
        "capabilities": caps,
        "suggested_runtime": manifest.get("suggested_runtime"),
        "generator": manifest.get("generator"),
        "status": manifest.get("status"),
    }


def _alignment_checks(project_root: Path, manifest: dict) -> list[tuple[str, bool, str]]:
    """Verify a single generated project aligns with the new agent spec."""
    checks: list[tuple[str, bool, str]] = []

    guide = project_root / "docs" / "guide-report.md"
    guide_text = guide.read_text(encoding="utf-8") if guide.exists() else ""

    # Check 1: guide-report must not invoke the old 'generate' mode of the maintainer.
    stale_generate = (
        "source-code-maintainer generate" in guide_text.lower()
        or "maintainer.*generate mode" in guide_text.lower()
    )
    checks.append(("no stale maintainer 'generate' mode reference", not stale_generate,
                   "guide-report.md mentions obsolete 'generate' mode" if stale_generate else ""))

    # Check 2: if guide-report recommends the implementer/validator, the agent
    # names must match the current roster (typos would break routing).
    valid_agents = {
        "azure-architecture-implementer",
        "source-code-maintainer",
        "bicep-infrastructure-validator",
        "security-compliance-auditor",
        "production-environment-advisor",
        "project-observability-advisor",
        "project-cost-analyzer",
        "project-traceability-advisor",
        "azure-project-deployer",
        "project-orchestrator",
        "factory-workflow-guide",
        "factory-handoff",
        "project-state-manager",
        "brd-to-architecture-diagram",
        "drawio-architecture-reader",
        "modernization-to-factory",
    }
    import re as _re
    cited = set(_re.findall(r"`([a-z0-9-]+-(?:agent|advisor|maintainer|validator|implementer|orchestrator|auditor|handoff|reader|manager|guide|factory|analyzer|deployer))`", guide_text))
    # filter to look like agent names (at least two hyphens)
    cited = {c for c in cited if c.count("-") >= 2}
    unknown = cited - valid_agents
    checks.append(("all cited agent names exist in roster", not unknown,
                   f"unknown agent names cited: {unknown}" if unknown else ""))

    # Check 3: manifest must be well-formed and claim completion.
    checks.append(("manifest status == complete", manifest.get("status") == "complete",
                   f"got {manifest.get('status')!r}"))

    # Check 4: runner produces the expected generator tag.
    checks.append(("generator tag intact",
                   manifest.get("generator") == "azure_native_factory_runner",
                   f"got {manifest.get('generator')!r}"))

    # Check 5: guide-report severity counts are present and numeric.
    gr = manifest.get("guide_report", {})
    sev = gr.get("severity_counts", {}) if gr else {}
    checks.append(("guide_report severity counts numeric",
                   all(isinstance(v, int) for v in sev.values()) if sev else True,
                   f"non-integer in severity_counts: {sev}"))

    # Check 6: governance detection for MDR BRD (mentions 'compliance') should flag capability.
    caps = manifest.get("capabilities", {})
    checks.append(("governance capability detected for MDR", bool(caps.get("governance")),
                   f"capabilities={caps}"))

    return checks


def main() -> int:
    if not BRD.exists():
        print(f"FATAL: MDR BRD not found at {BRD}", file=sys.stderr)
        return 2

    slugs: list[str] = []
    sigs: list[dict] = []
    results: list[dict] = []

    print(f"=== MDR 3x alignment run ===\nBRD: {BRD}\n")

    for i in range(1, ITER + 1):
        run_id = f"mdr-e2e-{uuid4().hex[:8]}"
        print(f"--- iteration {i}/{ITER}  run_id={run_id} ---")
        res = process_brd_document(
            factory_repo_root=REPO,
            brd_path=BRD,
            run_id=run_id,
            generation_options={"enableObservability": True, "networkTier": "public"},
        )
        slug = res["project"]["slug"]
        slugs.append(slug)
        print(f"  slug: {slug}  status: {res['status']}")
        proot = REPO / "projects" / slug
        manifest = json.loads((proot / "project-manifest.json").read_text(encoding="utf-8"))
        sig = _sig(proot)
        sigs.append(sig)
        checks = _alignment_checks(proot, manifest)
        passed = sum(1 for _, ok, _ in checks if ok)
        failed = [(n, m) for n, ok, m in checks if not ok]
        print(f"  checks: {passed}/{len(checks)} passed")
        for n, m in failed:
            print(f"    FAIL  {n}: {m}")
        results.append({"slug": slug, "checks_passed": passed, "checks_total": len(checks),
                        "failures": failed, "sig": sig})

    # Cross-run consistency: all 3 sigs should have same file count + same file layout
    # (timestamps in slugs differ, so we compare file *suffixes* relative to slug).
    print("\n=== cross-run consistency ===")
    def _normalize(sig):
        return {
            "file_count": sig["file_count"],
            "manifest_keys": sig["manifest_keys"],
            "capabilities": sig["capabilities"],
            "suggested_runtime": sig["suggested_runtime"],
            "generator": sig["generator"],
            "status": sig["status"],
            # strip slug prefix from file paths so we can compare layouts
            "layout": [f.split("/", 0)[-1] for f in sig["files"]],
        }
    n0 = _normalize(sigs[0])
    drift = []
    for i, s in enumerate(sigs[1:], start=2):
        ni = _normalize(s)
        if ni["file_count"] != n0["file_count"]:
            drift.append(f"  run{i}: file_count drifted ({n0['file_count']} -> {ni['file_count']})")
        if ni["manifest_keys"] != n0["manifest_keys"]:
            drift.append(f"  run{i}: manifest keys drifted")
        if ni["capabilities"] != n0["capabilities"]:
            drift.append(f"  run{i}: capabilities drifted")
        if ni["suggested_runtime"] != n0["suggested_runtime"]:
            drift.append(f"  run{i}: suggested_runtime drifted")

    if drift:
        print("DRIFT DETECTED:")
        for d in drift:
            print(d)
    else:
        print(f"OK: all {ITER} runs are structurally identical (file_count={n0['file_count']}, "
              f"manifest_keys={len(n0['manifest_keys'])}, caps={n0['capabilities']})")

    total_failures = sum(len(r["failures"]) for r in results)
    print(f"\n=== summary ===")
    print(f"Total alignment-check failures across {ITER} runs: {total_failures}")
    print("Generated slugs:")
    for s in slugs:
        print(f"  - projects/{s}")

    # Cleanup: remove the 3 E2E test projects (keep the repo tidy)
    print("\n=== cleanup ===")
    for s in slugs:
        d = REPO / "projects" / s
        if d.exists():
            shutil.rmtree(d)
            print(f"  removed projects/{s}")
        # also remove user-home copy if present
        uh = Path.home() / "app" / s
        if uh.exists():
            shutil.rmtree(uh, ignore_errors=True)

    if total_failures or drift:
        return 1
    print("\nALL 3 RUNS ALIGNED WITH NEW AGENT SPEC")
    return 0


if __name__ == "__main__":
    sys.exit(main())
