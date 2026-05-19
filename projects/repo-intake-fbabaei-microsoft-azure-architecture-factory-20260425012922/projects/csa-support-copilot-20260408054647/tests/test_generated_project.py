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
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert not missing, f'Missing generated docs: {missing}'


def test_deploy_guide_is_not_placeholder():
    root = Path(__file__).resolve().parents[1]
    content = (root / 'DEPLOY.md').read_text(encoding='utf-8')
    assert 'placeholder' not in content.lower()
    assert 'Prerequisites' in content
    assert 'Local Validation' in content
