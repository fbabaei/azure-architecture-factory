"""E2E harness: run a generic BRD through the factory 3 times on the DEFAULT
code path (Python + Bicep) and verify the pipeline is deterministic and
aligned with the current agent spec.

This is the AAF self-test for the default path. It is project-agnostic — the
BRD is written inline (tempfile) and deliberately mentions no specific domain,
customer, or sample so the factory can never regress by assuming a particular
project.

Mirrors scripts/dotnet_e2e_3x.py but targets python + bicep (the defaults
returned when a BRD does not declare `Implementation language:` /
`Infrastructure as code:`).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from local_brd_runner import process_brd_document  # type: ignore  # noqa: E402

ITER = 3

# A deliberately bland BRD: no language/iac hints, no customer-specific terms.
# The factory must honor its defaults (python + bicep) and produce a complete
# project without needing any sample-specific logic.
BRD_CONTENT = """# BRD — Default Path Smoke Test

**Status:** active

## Objective
Prove that the factory runner emits a complete project on the default code
path (Python + Bicep) deterministically, across multiple runs, from a BRD that
makes no language or IaC declarations.

## Requirements
- Expose a health endpoint returning 200.
- Expose one business endpoint that accepts and returns JSON.
- Ship a Dockerfile capable of building a production image.
- Provision an Azure compute surface plus supporting data/observability tier.
- Wire Application Insights when observability is enabled.

## Success criteria
- All generated files parse cleanly.
- Manifest records `implementation_language=python` and `iac_tool=bicep`
  (i.e., the defaults are honored when the BRD is silent).
"""


def _sig(project_root: Path) -> dict:
    files = sorted(
        str(p.relative_to(project_root)).replace("\\", "/")
        for p in project_root.rglob("*")
        if p.is_file()
    )
    manifest = json.loads((project_root / "project-manifest.json").read_text(encoding="utf-8"))
    return {
        "file_count": len(files),
        "files": files,
        "manifest_keys": sorted(manifest.keys()),
        "capabilities": manifest.get("capabilities", {}),
        "suggested_runtime": manifest.get("suggested_runtime"),
        "generator": manifest.get("generator"),
        "status": manifest.get("status"),
        "implementation_language": manifest.get("implementation_language"),
        "iac_tool": manifest.get("iac_tool"),
    }


_VALID_AGENTS = {
    "azure-architecture-implementer",
    "source-code-maintainer",
    "lang-dotnet-implementer",
    "bicep-infrastructure-validator",
    "terraform-infrastructure-validator",
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


def _alignment_checks(project_root: Path, manifest: dict) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    guide = project_root / "docs" / "guide-report.md"
    guide_text = guide.read_text(encoding="utf-8") if guide.exists() else ""

    stale_generate = "source-code-maintainer generate" in guide_text.lower()
    checks.append((
        "no stale maintainer 'generate' mode reference",
        not stale_generate,
        "guide-report.md mentions obsolete 'generate' mode" if stale_generate else "",
    ))

    cited = set(re.findall(
        r"`([a-z0-9-]+-(?:agent|advisor|maintainer|validator|implementer|orchestrator|auditor|handoff|reader|manager|guide|factory|analyzer|deployer))`",
        guide_text,
    ))
    cited = {c for c in cited if c.count("-") >= 2}
    unknown = cited - _VALID_AGENTS
    checks.append((
        "all cited agent names exist in roster",
        not unknown,
        f"unknown agent names cited: {unknown}" if unknown else "",
    ))

    checks.append((
        "manifest status == complete",
        manifest.get("status") == "complete",
        f"got {manifest.get('status')!r}",
    ))

    checks.append((
        "generator tag intact",
        manifest.get("generator") == "azure_native_factory_runner",
        f"got {manifest.get('generator')!r}",
    ))

    gr = manifest.get("guide_report", {})
    sev = gr.get("severity_counts", {}) if gr else {}
    checks.append((
        "guide_report severity counts numeric",
        all(isinstance(v, int) for v in sev.values()) if sev else True,
        f"non-integer in severity_counts: {sev}",
    ))

    # Default path must honor the defaults when the BRD is silent.
    checks.append((
        "default language is python",
        manifest.get("implementation_language") == "python",
        f"got {manifest.get('implementation_language')!r}",
    ))
    checks.append((
        "default iac is bicep",
        manifest.get("iac_tool") == "bicep",
        f"got {manifest.get('iac_tool')!r}",
    ))

    # Artifacts on disk must match the manifest claims.
    src_dir = project_root / "src"
    infra_dir = project_root / "infra"
    py_files = list(src_dir.rglob("*.py")) if src_dir.exists() else []
    cs_files = list(src_dir.rglob("*.cs")) if src_dir.exists() else []
    bicep_files = list(infra_dir.rglob("*.bicep")) if infra_dir.exists() else []
    tf_files = list(infra_dir.rglob("*.tf")) if infra_dir.exists() else []

    checks.append((
        "src/ contains Python sources",
        len(py_files) > 0,
        f".py count={len(py_files)}",
    ))
    checks.append((
        "src/ contains no .NET sources",
        len(cs_files) == 0,
        f".cs count={len(cs_files)}",
    ))
    checks.append((
        "infra/ contains Bicep modules",
        len(bicep_files) > 0,
        f".bicep count={len(bicep_files)}",
    ))
    checks.append((
        "infra/ contains no Terraform files",
        len(tf_files) == 0,
        f".tf count={len(tf_files)}",
    ))

    # Opt-in defaults: infra + security audit are on unless opted out.
    gen_opts = manifest.get("generation_options") or {}
    checks.append((
        "default generateInfra is true",
        gen_opts.get("generateInfra") is True,
        f"got {gen_opts.get('generateInfra')!r}",
    ))
    checks.append((
        "default runSecurityAudit is true",
        gen_opts.get("runSecurityAudit") is True,
        f"got {gen_opts.get('runSecurityAudit')!r}",
    ))

    return checks


def main() -> int:
    tmpdir = tempfile.mkdtemp(prefix="default-path-e2e-")
    brd = Path(tmpdir) / "default-path-smoke.md"
    brd.write_text(BRD_CONTENT, encoding="utf-8")

    slugs: list[str] = []
    sigs: list[dict] = []
    results: list[dict] = []

    print(f"=== Default path (Python + Bicep) 3x determinism run ===\nBRD: {brd}\n")

    try:
        for i in range(1, ITER + 1):
            run_id = f"default-e2e-{uuid4().hex[:8]}"
            print(f"--- iteration {i}/{ITER}  run_id={run_id} ---")
            res = process_brd_document(
                factory_repo_root=REPO,
                brd_path=brd,
                run_id=run_id,
                generation_options={"enableObservability": True, "networkTier": "public"},
            )
            slug = res["project"]["slug"]
            slugs.append(slug)
            manifest = json.loads((REPO / "projects" / slug / "project-manifest.json").read_text(encoding="utf-8"))
            print(f"  slug: {slug}  status: {res['status']}")
            print(f"  language: {manifest.get('implementation_language')}  iac: {manifest.get('iac_tool')}")
            proot = REPO / "projects" / slug
            sig = _sig(proot)
            sigs.append(sig)
            checks = _alignment_checks(proot, manifest)
            passed = sum(1 for _, ok, _ in checks if ok)
            failed = [(n, m) for n, ok, m in checks if not ok]
            print(f"  checks: {passed}/{len(checks)} passed")
            for n, m in failed:
                print(f"    FAIL  {n}: {m}")
            results.append({"slug": slug, "failures": failed, "sig": sig})

        print("\n=== cross-run consistency ===")

        def _normalize(sig, slug):
            layout = [f.replace(slug, "{slug}") for f in sig["files"]]
            return {
                "file_count": sig["file_count"],
                "manifest_keys": sig["manifest_keys"],
                "capabilities": sig["capabilities"],
                "suggested_runtime": sig["suggested_runtime"],
                "generator": sig["generator"],
                "status": sig["status"],
                "implementation_language": sig["implementation_language"],
                "iac_tool": sig["iac_tool"],
                "layout": layout,
            }

        n0 = _normalize(sigs[0], slugs[0])
        drift: list[str] = []
        for i, (s, slug) in enumerate(zip(sigs[1:], slugs[1:]), start=2):
            ni = _normalize(s, slug)
            if ni["file_count"] != n0["file_count"]:
                drift.append(f"  run{i}: file_count drifted ({n0['file_count']} -> {ni['file_count']})")
            if ni["manifest_keys"] != n0["manifest_keys"]:
                drift.append(f"  run{i}: manifest keys drifted")
            if ni["capabilities"] != n0["capabilities"]:
                drift.append(f"  run{i}: capabilities drifted")
            if ni["implementation_language"] != n0["implementation_language"]:
                drift.append(f"  run{i}: implementation_language drifted")
            if ni["iac_tool"] != n0["iac_tool"]:
                drift.append(f"  run{i}: iac_tool drifted")
            if ni["layout"] != n0["layout"]:
                drift.append(f"  run{i}: file layout drifted")

        if drift:
            print("DRIFT DETECTED:")
            for d in drift:
                print(d)
        else:
            print(
                f"OK: all {ITER} runs are structurally identical "
                f"(file_count={n0['file_count']}, language={n0['implementation_language']}, "
                f"iac={n0['iac_tool']})"
            )

        total_failures = sum(len(r["failures"]) for r in results)
        print("\n=== summary ===")
        print(f"Total alignment-check failures across {ITER} runs: {total_failures}")
        print("Generated slugs:")
        for s in slugs:
            print(f"  - projects/{s}")
    finally:
        print("\n=== cleanup ===")
        for s in slugs:
            d = REPO / "projects" / s
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                print(f"  removed projects/{s}")
            uh = Path.home() / "app" / s
            if uh.exists():
                shutil.rmtree(uh, ignore_errors=True)
        shutil.rmtree(tmpdir, ignore_errors=True)

    if 'total_failures' in locals() and (total_failures or drift):
        return 1
    print("\nALL 3 DEFAULT-PATH RUNS ARE DETERMINISTIC AND ALIGNED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
