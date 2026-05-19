"""Run the MDR BRD three times through the .NET language agent and assert determinism.

Asserts:
- archetype == 'extraction-chat' in every run's project-manifest.json
- each run writes the same file set (modulo slug-specific paths)
- expected extraction-chat files present (Services/*, Models.cs, sample-corpus/, detailed-architecture)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from local_brd_runner import process_brd_document  # noqa: E402

BRD = ROOT / "docs" / "intake" / "mdr-support.md"

EXPECTED_EXTRACTION_FILES = {
    "src/Program.cs",
    "src/Models.cs",
    "src/Services/DocumentIngestionService.cs",
    "src/Services/ExtractionService.cs",
    "src/Services/ClarificationService.cs",
    "src/Services/DraftRepository.cs",
    "src/Services/SessionService.cs",
    "src/Dockerfile",
    "global.json",
    "sample-corpus/README.md",
    "sample-corpus/manifest.json",
    "docs/detailed-architecture.md",
    "README.md",
    "DEPLOY.md",
}


def relpath(project_root: Path, p: Path) -> str:
    return str(p.relative_to(project_root)).replace("\\", "/")


def collect_files(project_root: Path) -> set[str]:
    files: set[str] = set()
    for p in project_root.rglob("*"):
        if p.is_file():
            rel = relpath(project_root, p)
            # Skip generated logs that include timestamps / process-specific ids.
            if rel.startswith("logs/"):
                continue
            files.add(rel)
    return files


def main() -> int:
    runs: list[tuple[str, Path, set[str]]] = []
    for i in range(3):
        run_id = f"mdrnet{i:02d}"
        # Clean any prior attempt with the same run id.
        for old in (ROOT / "projects").glob(f"*-{run_id}"):
            shutil.rmtree(old, ignore_errors=True)

        result = process_brd_document(
            factory_repo_root=ROOT,
            brd_path=BRD,
            run_id=run_id,
            generation_options={
                "implementationLanguage": "dotnet",
                "iacTool": "bicep",
                "generateInfra": True,
                "runSecurityAudit": True,
                "enableObservability": True,
            },
        )
        slug = result["project"]["slug"]
        project_root = ROOT / "projects" / slug
        manifest = json.loads((project_root / "project-manifest.json").read_text(encoding="utf-8"))
        archetype = manifest.get("analysis", {}).get("archetype") or manifest.get("archetype")
        if archetype != "extraction-chat":
            print(f"[FAIL] run {i}: archetype={archetype!r} (expected extraction-chat)")
            return 1

        files = collect_files(project_root)
        missing = EXPECTED_EXTRACTION_FILES - files
        if missing:
            print(f"[FAIL] run {i}: missing expected files {sorted(missing)}")
            return 1

        print(f"[run {i}] slug={project_root.name} files={len(files)} archetype={archetype}")
        runs.append((run_id, project_root, files))

    # Determinism: compare file *sets* across runs (slug differs per run_id by design).
    base_run_id, base_root, base_files = runs[0]

    def strip_slug(files: set[str], slug: str) -> set[str]:
        # The slug appears in diagrams/<slug>.{drawio,md}; normalize those.
        out = set()
        for f in files:
            if f.startswith(f"diagrams/{slug}"):
                out.add(f.replace(slug, "<SLUG>"))
            else:
                out.add(f)
        return out

    base_normalized = strip_slug(base_files, base_root.name)
    for run_id, project_root, files in runs[1:]:
        normalized = strip_slug(files, project_root.name)
        if normalized != base_normalized:
            only_base = sorted(base_normalized - normalized)
            only_this = sorted(normalized - base_normalized)
            print(f"[FAIL] run {run_id}: file set differs from base {base_run_id}")
            print(f"  only in base:  {only_base}")
            print(f"  only in this: {only_this}")
            return 1

    print(f"[OK] 3x deterministic: {len(base_normalized)} files, archetype=extraction-chat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
