"""E2E harness: run the .NET + Terraform BRD through the factory 3 times and
verify the language + IaC agent registries emit the right artifacts deterministically.

Peer of scripts/default_path_e2e_3x.py but targets the dotnet + terraform code
paths exposed by the scripts/language_agents + scripts/iac_agents packages.

The BRD is written inline (as a tempfile) so this harness is fully self-contained
and does not depend on docs/intake/ (which is gitignored).
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

from local_brd_runner import process_brd_document  # type: ignore  # noqa: E402

ITER = 3

BRD_CONTENT = """# BRD — .NET + Terraform Smoke Test

**Status:** active
**Implementation language:** dotnet
**Infrastructure as code:** terraform

## Objective
Prove that the factory runner can emit a .NET 8 minimal API plus a Terraform
infra module when the BRD requests them, deterministically, across multiple
runs.

## Requirements
- Expose `/health` endpoint returning 200.
- Expose `/api/ask` endpoint accepting `{"question": str}` and returning `{"answer": str}`.
- Build into a container image via the emitted Dockerfile.
- Provision Azure Container Apps infrastructure via Terraform (azurerm).
- Emit Log Analytics + Application Insights when observability is enabled.
- Governance and compliance logging must be available.

## Success criteria
- All generated files parse cleanly (no syntax errors).
- Manifest records `implementation_language=dotnet` and `iac_tool=terraform`.

## Network tier
standard
"""


def _sig(project_root: Path) -> dict:
    files = sorted(
        str(p.relative_to(project_root)).replace("\\", "/")
        for p in project_root.rglob("*")
        if p.is_file()
    )
    manifest = json.loads(
        (project_root / "project-manifest.json").read_text(encoding="utf-8")
    )
    return {
        "file_count": len(files),
        "files": files,
        "manifest_keys": sorted(manifest.keys()),
        "implementation_language": manifest.get("implementation_language"),
        "iac_tool": manifest.get("iac_tool"),
        "language_files_count": len(manifest.get("language_files", [])),
        "iac_files_count": len(manifest.get("iac_files", [])),
        "capabilities": manifest.get("capabilities", {}),
        "generator": manifest.get("generator"),
        "status": manifest.get("status"),
    }


def _alignment_checks(
    project_root: Path, manifest: dict
) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    # 1. Language + IaC selection recorded in manifest
    checks.append((
        "manifest.implementation_language == dotnet",
        manifest.get("implementation_language") == "dotnet",
        f"got {manifest.get('implementation_language')!r}",
    ))
    checks.append((
        "manifest.iac_tool == terraform",
        manifest.get("iac_tool") == "terraform",
        f"got {manifest.get('iac_tool')!r}",
    ))

    # 2. .NET source artifacts
    src = project_root / "src"
    csprojs = list(src.glob("*.csproj"))
    checks.append((
        "exactly one src/*.csproj emitted",
        len(csprojs) == 1,
        f"found {len(csprojs)}",
    ))
    dotnet_required = [
        "src/Program.cs",
        "src/appsettings.json",
        "src/appsettings.Development.json",
        "src/Dockerfile",
        "src/.dockerignore",
        "global.json",
    ]
    for rel in dotnet_required:
        p = project_root / rel
        checks.append((f"{rel} exists", p.exists(), f"missing {rel}"))

    # 3. Program.cs endpoint shape (health + group-routed ask)
    if (src / "Program.cs").exists():
        program = (src / "Program.cs").read_text(encoding="utf-8")
        checks.append((
            "Program.cs MapGet /health",
            "MapGet(\"/health\"" in program,
            "/health not found",
        ))
        checks.append((
            "Program.cs POST /ask handler",
            "MapPost(\"/ask\"" in program,
            "/ask POST handler not found",
        ))

    # 4. Dockerfile uses the .NET SDK + ASP.NET runtime images
    dockerfile = src / "Dockerfile"
    if dockerfile.exists():
        df = dockerfile.read_text(encoding="utf-8")
        checks.append((
            "Dockerfile uses dotnet/sdk base image",
            "mcr.microsoft.com/dotnet/sdk" in df,
            "sdk base image missing",
        ))
        checks.append((
            "Dockerfile uses dotnet/aspnet runtime image",
            "mcr.microsoft.com/dotnet/aspnet" in df,
            "aspnet runtime image missing",
        ))

    # 5. Terraform infra artifacts
    tf_required = [
        "infra/main.tf",
        "infra/providers.tf",
        "infra/variables.tf",
        "infra/outputs.tf",
        "infra/terraform.tfvars.example",
    ]
    for rel in tf_required:
        p = project_root / rel
        checks.append((f"{rel} exists", p.exists(), f"missing {rel}"))

    # 6. Terraform content sanity
    providers = project_root / "infra" / "providers.tf"
    if providers.exists():
        pv = providers.read_text(encoding="utf-8")
        checks.append((
            "providers.tf declares azurerm provider",
            "azurerm" in pv and "hashicorp/azurerm" in pv,
            "azurerm provider not declared correctly",
        ))
        checks.append((
            "providers.tf pins required_version",
            "required_version" in pv,
            "required_version missing",
        ))

    main_tf = project_root / "infra" / "main.tf"
    if main_tf.exists():
        mt = main_tf.read_text(encoding="utf-8")
        checks.append((
            "main.tf uses data resource group lookup",
            "data \"azurerm_resource_group\"" in mt,
            "resource group data block missing",
        ))
        checks.append((
            "main.tf conditionally emits Log Analytics",
            "azurerm_log_analytics_workspace" in mt
            and "var.enable_observability" in mt,
            "log analytics / enable_observability not wired",
        ))
        checks.append((
            "main.tf conditionally emits Application Insights",
            "azurerm_application_insights" in mt,
            "application insights resource missing",
        ))

    vars_tf = project_root / "infra" / "variables.tf"
    if vars_tf.exists():
        vt = vars_tf.read_text(encoding="utf-8")
        checks.append((
            "variables.tf defines enable_observability",
            "variable \"enable_observability\"" in vt,
            "enable_observability var missing",
        ))

    # 7. The *old* (Python + Bicep) paths must NOT have emitted
    checks.append((
        "no stray src/copilot_api tree",
        not (project_root / "src" / "copilot_api").exists(),
        "python source tree leaked into dotnet run",
    ))
    checks.append((
        "no stray infra/main.bicep",
        not (project_root / "infra" / "main.bicep").exists(),
        "bicep module leaked into terraform run",
    ))
    checks.append((
        "no stray requirements.txt",
        not (project_root / "requirements.txt").exists(),
        "python requirements.txt leaked into dotnet run",
    ))

    # 8. Standard manifest hygiene
    checks.append((
        "manifest.status == complete",
        manifest.get("status") == "complete",
        f"got {manifest.get('status')!r}",
    ))
    checks.append((
        "generator tag intact",
        manifest.get("generator") == "azure_native_factory_runner",
        f"got {manifest.get('generator')!r}",
    ))

    # 9. Shared docs still emit regardless of language/IaC choice
    shared_docs = [
        "docs/architecture-overview.md",
        "docs/governance-model.md",
        "docs/delivery-milestones.md",
        "docs/success-criteria.md",
        "docs/traceability-matrix.md",
        "README.md",
        "DEPLOY.md",
    ]
    for rel in shared_docs:
        checks.append((
            f"{rel} exists",
            (project_root / rel).exists(),
            f"missing shared doc {rel}",
        ))

    return checks


def main() -> int:
    # Write the BRD to a tempfile so the harness is self-contained.
    tmpdir = Path(tempfile.mkdtemp(prefix="dotnet-tf-e2e-"))
    brd_path = tmpdir / "dotnet-terraform-smoke.md"
    brd_path.write_text(BRD_CONTENT, encoding="utf-8")

    slugs: list[str] = []
    sigs: list[dict] = []
    results: list[dict] = []

    print(f"=== .NET + Terraform 3x determinism run ===\nBRD: {brd_path}\n")

    try:
        for i in range(1, ITER + 1):
            run_id = f"dotnet-tf-e2e-{uuid4().hex[:8]}"
            print(f"--- iteration {i}/{ITER}  run_id={run_id} ---")
            res = process_brd_document(
                factory_repo_root=REPO,
                brd_path=brd_path,
                run_id=run_id,
                generation_options={
                    "enableObservability": True,
                    "networkTier": "public",
                },
            )
            slug = res["project"]["slug"]
            slugs.append(slug)
            proot = REPO / "projects" / slug
            print(f"  slug: {slug}  status: {res['status']}")
            print(f"  language: {res.get('analysis', {}).get('implementationLanguage')}  "
                  f"iac: {res.get('analysis', {}).get('iacTool')}")

            manifest = json.loads(
                (proot / "project-manifest.json").read_text(encoding="utf-8")
            )
            sig = _sig(proot)
            sigs.append(sig)
            checks = _alignment_checks(proot, manifest)
            passed = sum(1 for _, ok, _ in checks if ok)
            failed = [(n, m) for n, ok, m in checks if not ok]
            print(f"  checks: {passed}/{len(checks)} passed")
            for n, m in failed:
                print(f"    FAIL  {n}: {m}")
            results.append({
                "slug": slug,
                "checks_passed": passed,
                "checks_total": len(checks),
                "failures": failed,
                "sig": sig,
            })

        # Cross-run consistency
        print("\n=== cross-run consistency ===")

        def _normalize(sig: dict, slug: str) -> dict:
            # Some filenames embed the slug (e.g. diagrams/{slug}.drawio); replace
            # them with a <SLUG> placeholder so layouts compare across runs.
            layout = sorted({
                f.replace(slug, "<SLUG>") for f in sig["files"]
            })
            return {
                "file_count": sig["file_count"],
                "manifest_keys": sig["manifest_keys"],
                "implementation_language": sig["implementation_language"],
                "iac_tool": sig["iac_tool"],
                "language_files_count": sig["language_files_count"],
                "iac_files_count": sig["iac_files_count"],
                "capabilities": sig["capabilities"],
                "generator": sig["generator"],
                "status": sig["status"],
                "layout": layout,
            }

        n0 = _normalize(sigs[0], slugs[0])
        drift: list[str] = []
        for i, s in enumerate(sigs[1:], start=2):
            ni = _normalize(s, slugs[i - 1])
            if ni["file_count"] != n0["file_count"]:
                drift.append(
                    f"  run{i}: file_count drifted "
                    f"({n0['file_count']} -> {ni['file_count']})"
                )
            if ni["manifest_keys"] != n0["manifest_keys"]:
                drift.append(f"  run{i}: manifest keys drifted")
            if ni["implementation_language"] != n0["implementation_language"]:
                drift.append(
                    f"  run{i}: implementation_language drifted "
                    f"({n0['implementation_language']!r} -> {ni['implementation_language']!r})"
                )
            if ni["iac_tool"] != n0["iac_tool"]:
                drift.append(
                    f"  run{i}: iac_tool drifted "
                    f"({n0['iac_tool']!r} -> {ni['iac_tool']!r})"
                )
            if ni["language_files_count"] != n0["language_files_count"]:
                drift.append(
                    f"  run{i}: language_files_count drifted "
                    f"({n0['language_files_count']} -> {ni['language_files_count']})"
                )
            if ni["iac_files_count"] != n0["iac_files_count"]:
                drift.append(
                    f"  run{i}: iac_files_count drifted "
                    f"({n0['iac_files_count']} -> {ni['iac_files_count']})"
                )
            if ni["layout"] != n0["layout"]:
                extra = set(ni["layout"]) - set(n0["layout"])
                missing = set(n0["layout"]) - set(ni["layout"])
                drift.append(
                    f"  run{i}: file layout drifted "
                    f"(+{sorted(extra)} -{sorted(missing)})"
                )

        if drift:
            print("DRIFT DETECTED:")
            for d in drift:
                print(d)
        else:
            print(
                f"OK: all {ITER} runs are structurally identical "
                f"(file_count={n0['file_count']}, "
                f"language={n0['implementation_language']}, "
                f"iac={n0['iac_tool']}, "
                f"language_files={n0['language_files_count']}, "
                f"iac_files={n0['iac_files_count']})"
            )

        total_failures = sum(len(r["failures"]) for r in results)
        print("\n=== summary ===")
        print(
            f"Total alignment-check failures across {ITER} runs: {total_failures}"
        )
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
            uh = Path.home() / "app" / s
            if uh.exists():
                shutil.rmtree(uh, ignore_errors=True)

        if total_failures or drift:
            return 1
        print("\nALL 3 .NET + TERRAFORM RUNS ARE DETERMINISTIC AND ALIGNED")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
