from pathlib import Path


def test_project_e_artifacts_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        root / "README.md",
        root / "DEPLOY.md",
        root / "docs" / "architecture-overview.md",
        root / "docs" / "governance-model.md",
        root / "docs" / "delivery-milestones.md",
        root / "docs" / "success-criteria.md",
        root / "docs" / "traceability-matrix.md",
        root / "diagrams" / "project-e-ticket-triage-assistant.md",
        root / "diagrams" / "project-e-ticket-triage-assistant.drawio",
        root / "project-manifest.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f"Missing project artifacts: {missing}"
