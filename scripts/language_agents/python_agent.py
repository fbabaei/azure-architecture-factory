"""Python / FastAPI language specialist.

DEFAULT language agent — matches the pre-refactor behaviour of
`scripts/local_brd_runner.py` exactly. Emits:

    src/copilot_api/__init__.py
    src/copilot_api/main.py
    src/copilot_api/models.py
    src/copilot_api/services/__init__.py
    src/copilot_api/services/copilot_service.py
    requirements.txt
    pyproject.toml
    tests/test_generated_project.py
    README.md
    DEPLOY.md
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import LanguageAgent, LanguageEmitContext, LanguageEmitResult


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return normalized.strip("-") or "project"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _build_api_main() -> str:
    return (
        "from datetime import datetime, timezone\n"
        "from fastapi import FastAPI\n\n"
        "from .models import AskRequest, AskResponse\n"
        "from .services.copilot_service import build_response\n\n\n"
        "app = FastAPI(title=\"Generated Copilot API\", version=\"0.1.0\")\n\n\n"
        "@app.get(\"/health\")\n"
        "def health() -> dict:\n"
        "    return {\"status\": \"ok\", \"timestamp\": datetime.now(timezone.utc).isoformat()}\n\n\n"
        "@app.post(\"/api/copilot/ask\", response_model=AskResponse)\n"
        "def ask_copilot(payload: AskRequest) -> AskResponse:\n"
        "    return AskResponse(answer=build_response(payload.question, payload.context), source=\"generated-starter\")\n"
    )


def _build_api_models() -> str:
    return (
        "from pydantic import BaseModel, Field\n\n\n"
        "class AskRequest(BaseModel):\n"
        "    question: str = Field(min_length=3)\n"
        "    context: str = Field(default=\"\")\n\n\n"
        "class AskResponse(BaseModel):\n"
        "    answer: str\n"
        "    source: str\n"
    )


def _build_api_service() -> str:
    return (
        "def build_response(question: str, context: str) -> str:\n"
        "    summary = context.strip()[:240]\n"
        "    if summary:\n"
        "        return \"Starter copilot response for question: '\" + question + \"'. Context summary: \" + summary + \". Replace this logic with your workload-specific orchestration.\"\n"
        "    return \"Starter copilot response for question: '\" + question + \"'. Replace this logic with your workload-specific orchestration.\"\n"
    )


def _build_pyproject(title: str) -> str:
    normalized = _slugify(title).replace("-", "_")
    return (
        f"[project]\n"
        f"name = \"{normalized}\"\n"
        f"version = \"0.1.0\"\n"
        f"description = \"Generated starter project for {title}\"\n"
        f"requires-python = \">=3.11\"\n"
        f"dependencies = [\n"
        f"  \"fastapi==0.116.1\",\n"
        f"  \"uvicorn[standard]==0.32.1\",\n"
        f"  \"pydantic==2.10.3\",\n"
        f"]\n"
    )


def _build_test() -> str:
    return (
        "from pathlib import Path\n\n\n"
        "def test_generated_project_docs_exist():\n"
        "    root = Path(__file__).resolve().parents[1]\n"
        "    required = [\n"
        "        root / 'README.md',\n"
        "        root / 'DEPLOY.md',\n"
        "        root / 'requirements.txt',\n"
        "        root / 'src' / 'copilot_api' / 'main.py',\n"
        "        root / 'src' / 'copilot_api' / 'models.py',\n"
        "        root / 'src' / 'copilot_api' / 'services' / 'copilot_service.py',\n"
        "        root / 'docs' / 'architecture-overview.md',\n"
        "        root / 'docs' / 'governance-model.md',\n"
        "        root / 'docs' / 'delivery-milestones.md',\n"
        "        root / 'docs' / 'success-criteria.md',\n"
        "        root / 'docs' / 'traceability-matrix.md',\n"
        "        root / 'diagrams' / (root.name + '.md'),\n"
        "        root / 'project-manifest.json',\n"
        "    ]\n"
        "    missing = [str(path) for path in required if not path.exists()]\n"
        "    assert not missing, f'Missing generated docs: {missing}'\n"
    )


def _build_readme(title: str, source_brd: str, slug: str, requirements: list[str], enable_observability: bool) -> str:
    highlights = "\n".join(f"- {item}" for item in requirements[:10])
    observability_line = (
        "- Monitoring and observability wiring requested: Yes"
        if enable_observability
        else "- Monitoring and observability wiring requested: No"
    )
    return (
        f"# {title}\n\n"
        f"Generated from BRD `{source_brd}` by the Azure-native factory runner (Python specialist).\n\n"
        f"## Implementation Language\n\n"
        f"**Python 3.11+ (FastAPI)**\n\n"
        f"## What Was Generated\n"
        f"- `docs/architecture-overview.md`\n"
        f"- `docs/governance-model.md`\n"
        f"- `docs/delivery-milestones.md`\n"
        f"- `docs/success-criteria.md`\n"
        f"- `docs/traceability-matrix.md`\n"
        f"- `diagrams/{slug}.md`\n"
        f"- `diagrams/{slug}.drawio`\n"
        f"- `src/copilot_api/main.py`\n"
        f"- `src/copilot_api/models.py`\n"
        f"- `src/copilot_api/services/copilot_service.py`\n"
        f"- `requirements.txt`\n"
        f"- `tests/test_generated_project.py`\n\n"
        f"## Selected Generation Options\n{observability_line}\n\n"
        f"## BRD Requirement Highlights\n{highlights}\n"
    )


def _build_deploy(slug: str, enable_observability: bool) -> str:
    deployment_steps = [
        "1. Review and customize `infra/main.bicep`.",
        "2. Provision hosting, identity, Key Vault access, and Application Insights.",
        "3. Configure application settings for the generated API.",
        f"4. Deploy the project from `projects/{slug}`.",
        "5. Validate `/health` after deployment.",
    ]
    if enable_observability:
        deployment_steps[1] = (
            "2. Provision hosting, identity, Key Vault access, Application Insights, and Log Analytics."
        )
        deployment_steps.insert(
            3,
            "4. Configure health probes, alerts, dashboards, and operational ownership for the generated workload.",
        )
        deployment_steps[4] = f"5. Deploy the project from `projects/{slug}`."
        deployment_steps[5] = "6. Validate `/health` after deployment and confirm telemetry reaches Azure Monitor."
    return (
        "# Deploy\n\n"
        "## Prerequisites\n"
        "- Python 3.11+\n"
        "- Azure CLI authenticated\n"
        "- Target Azure subscription and resource group\n\n"
        "## Local Validation\n"
        "```bash\n"
        "python -m venv .venv\n"
        ".venv\\Scripts\\activate\n"
        "python -m pip install -r requirements.txt\n"
        "python -m pytest tests -q\n"
        "```\n\n"
        "## Local Run\n"
        "```bash\n"
        "python -m uvicorn src.copilot_api.main:app --host 127.0.0.1 --port 8000 --reload\n"
        "```\n\n"
        "## Azure Deployment Outline\n"
        + "\n".join(deployment_steps)
        + "\n"
    )


class PythonAgent:
    name = "python"
    display_name = "Python (FastAPI)"

    def emit(self, ctx: LanguageEmitContext) -> LanguageEmitResult:
        project_root = ctx.project_root
        src_dir = project_root / "src" / "copilot_api"
        services_dir = src_dir / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        ctx.tests_dir.mkdir(parents=True, exist_ok=True)

        _write_text(src_dir / "__init__.py", "")
        _write_text(src_dir / "main.py", _build_api_main())
        _write_text(src_dir / "models.py", _build_api_models())
        _write_text(services_dir / "__init__.py", "")
        _write_text(services_dir / "copilot_service.py", _build_api_service())
        _write_text(
            project_root / "requirements.txt",
            "fastapi==0.116.1\nuvicorn[standard]==0.32.1\npydantic==2.10.3\n",
        )
        _write_text(project_root / "pyproject.toml", _build_pyproject(ctx.title))
        _write_text(ctx.tests_dir / "test_generated_project.py", _build_test())
        _write_text(
            project_root / "README.md",
            _build_readme(ctx.title, ctx.source_brd, ctx.slug, ctx.requirements, ctx.enable_observability),
        )
        _write_text(project_root / "DEPLOY.md", _build_deploy(ctx.slug, ctx.enable_observability))

        return LanguageEmitResult(
            files_written=[
                "src/copilot_api/__init__.py",
                "src/copilot_api/main.py",
                "src/copilot_api/models.py",
                "src/copilot_api/services/__init__.py",
                "src/copilot_api/services/copilot_service.py",
                "requirements.txt",
                "pyproject.toml",
                "tests/test_generated_project.py",
                "README.md",
                "DEPLOY.md",
            ],
            readme_bullets=[
                "- Python 3.11+ FastAPI starter with health endpoint",
                "- pytest scaffold validating generated project shape",
            ],
        )


AGENT = PythonAgent()
