from pathlib import Path


def test_generated_project_docs_exist():
    root = Path(__file__).resolve().parents[1]
    required = [
        root / 'README.md',
        root / 'DEPLOY.md',
        root / 'requirements.txt',
        root / 'src' / 'copilot_api' / 'main.py',
        root / 'src' / 'copilot_api' / 'models.py',
        root / 'src' / 'copilot_api' / 'services' / 'copilot_service.py',
        root / 'docs' / 'architecture-overview.md',
        root / 'docs' / 'governance-model.md',
        root / 'docs' / 'delivery-milestones.md',
        root / 'docs' / 'success-criteria.md',
        root / 'docs' / 'traceability-matrix.md',
        root / 'diagrams' / (root.name + '.md'),
        root / 'project-manifest.json',
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f'Missing generated docs: {missing}'
