from pathlib import Path

def test_generated_project_docs_exist():
    root = Path(__file__).resolve().parents[1]
    required = [
        root / 'README.md',
        root / 'docs' / 'architecture-overview.md',
        root / 'docs' / 'governance-model.md',
        root / 'docs' / 'delivery-milestones.md',
        root / 'docs' / 'success-criteria.md',
        root / 'docs' / 'traceability-matrix.md',
        root / 'diagrams' / (root.name + '.md'),
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f'Missing generated docs: {missing}'
