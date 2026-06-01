from pathlib import Path


def test_generated_project_docs_exist():
    root = Path(__file__).resolve().parents[1]
    required = [
        root / 'README.md',
        root / 'DEPLOY.md',
        root / 'requirements.txt',
        root / 'src' / 'mdr_support' / 'main.py',
        root / 'src' / 'mdr_support' / 'models.py',
        root / 'docs' / 'architecture-overview.md',
        root / 'docs' / 'governance-model.md',
        root / 'docs' / 'delivery-milestones.md',
        root / 'docs' / 'success-criteria.md',
        root / 'docs' / 'traceability-matrix.md',
        root / 'diagrams' / (root.name + '.md'),
        root / 'project-manifest.json',
        root / 'src' / 'mdr_support' / 'services' / 'document_ingestion.py',
        root / 'src' / 'mdr_support' / 'services' / 'extraction_service.py',
        root / 'src' / 'mdr_support' / 'services' / 'clarification_service.py',
        root / 'src' / 'mdr_support' / 'services' / 'repository.py',
        root / 'src' / 'mdr_support' / 'services' / 'session_service.py',
        root / 'sample-corpus' / 'manifest.json',
        root / 'docs' / 'detailed-architecture.md',
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f'Missing generated docs: {missing}'
