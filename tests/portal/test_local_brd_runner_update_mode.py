from __future__ import annotations

import json
from pathlib import Path

import local_brd_runner as runner


def _write_brd(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_process_brd_document_reuses_target_slug_and_snapshots_previous_project(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(runner, "generate_guide_report", lambda project_root, brd_path: {})
    monkeypatch.setattr(runner, "_copy_project_to_user_home", lambda project_root, slug: tmp_path / "home" / slug)

    initial_brd = repo_root / "initial.md"
    _write_brd(
        initial_brd,
        "# Initial Project\n\n## Key Requirements\n- Expose an HTTP API\n- Store audit data\n",
    )

    initial_result = runner.process_brd_document(
        repo_root,
        initial_brd,
        "run-1",
        {"generateInfra": False},
    )
    slug = initial_result["project"]["slug"]
    project_root = repo_root / "projects" / slug
    marker = project_root / "custom.txt"
    marker.write_text("preserve via snapshot", encoding="utf-8")

    updated_brd = repo_root / "updated.md"
    _write_brd(
        updated_brd,
        "# Updated Project\n\n## Key Requirements\n- Expose an HTTP API\n- Add a worker service\n",
    )

    updated_result = runner.process_brd_document(
        repo_root,
        updated_brd,
        "run-2",
        {"generateInfra": False, "targetProjectSlug": slug, "sourceType": "mermaid"},
    )

    assert updated_result["project"]["slug"] == slug

    history_root = repo_root / "projects" / "_history" / slug
    snapshots = sorted(history_root.iterdir())
    assert snapshots
    assert (snapshots[-1] / "custom.txt").is_file()
    assert not marker.exists()

    manifest = json.loads((project_root / "project-manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_type"] == "mermaid"
    assert manifest["update"]["target_project"] == slug
