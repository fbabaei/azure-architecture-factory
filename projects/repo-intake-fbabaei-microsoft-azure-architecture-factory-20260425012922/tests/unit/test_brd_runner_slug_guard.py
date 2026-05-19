"""Regression test for the BRD runner slug-collision guard.

Two BRD runs kicked off within the same second must produce distinct project
folders, not overwrite each other. Prior to the guard, the slug was derived
only from `%Y%m%d%H%M%S` precision.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from local_brd_runner import process_brd_document  # type: ignore


@pytest.fixture
def brd_path() -> Path:
    p = REPO / "docs" / "intake" / "mdr-support.md"
    if not p.exists():
        pytest.skip(f"BRD not found at {p}")
    return p


def test_back_to_back_runs_do_not_collide(tmp_path, brd_path):
    """Running the BRD runner three times back-to-back must produce three
    distinct project directories, each with a complete manifest."""
    factory_root = tmp_path / "factory"
    factory_root.mkdir()
    # Mirror the minimal structure the runner touches.
    (factory_root / "docs" / "intake").mkdir(parents=True)
    shutil.copy(brd_path, factory_root / "docs" / "intake" / "mdr-support.md")
    (factory_root / "projects").mkdir()
    (factory_root / "outputs" / "brd-runs").mkdir(parents=True)

    slugs: list[str] = []
    for _ in range(3):
        res = process_brd_document(
            factory_repo_root=factory_root,
            brd_path=factory_root / "docs" / "intake" / "mdr-support.md",
            run_id=f"regression-{uuid4().hex[:8]}",
            generation_options={"enableObservability": False, "networkTier": "public"},
        )
        assert res["status"] == "complete"
        slugs.append(res["project"]["slug"])

    # Core invariant: all three slugs are distinct and all three folders exist.
    assert len(set(slugs)) == 3, f"slug collision: {slugs}"
    for slug in slugs:
        proj = factory_root / "projects" / slug
        assert proj.exists(), f"missing project folder for {slug}"
        manifest = json.loads((proj / "project-manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "complete"
        assert manifest["generator"] == "azure_native_factory_runner"

    # Cleanup user-home copies so the test is hermetic.
    for slug in slugs:
        uh = Path.home() / "app" / slug
        if uh.exists():
            shutil.rmtree(uh, ignore_errors=True)
