from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def process_brd_document(factory_repo_root: Path, brd_path: Path, run_id: str) -> dict[str, Any]:
    brd_text = brd_path.read_text(encoding="utf-8")
    generated_at = datetime.now(timezone.utc)
    generated_at_iso = generated_at.isoformat().replace("+00:00", "Z")
    timestamp = generated_at.strftime("%Y%m%d%H%M%S")

    title = _extract_title(brd_text, brd_path.stem)
    requirements = _extract_requirements(brd_text)
    success_criteria = _extract_success_criteria(brd_text)
    capabilities = _infer_capabilities(brd_text)
    slug = f"{_slugify(title)}-{timestamp}"

    project_root = factory_repo_root / "projects" / slug
    diagrams_dir = project_root / "diagrams"
    docs_dir = project_root / "docs"
    src_dir = project_root / "src" / "copilot_api"
    services_dir = src_dir / "services"
    tests_dir = project_root / "tests"
    infra_dir = project_root / "infra"
    logs_dir = project_root / "logs"
    outputs_dir = factory_repo_root / "outputs" / "brd-runs"

    for path in [diagrams_dir, docs_dir, services_dir, tests_dir, infra_dir, logs_dir, outputs_dir]:
        path.mkdir(parents=True, exist_ok=True)

    diagram_basename = f"{slug}.drawio"
    diagram_notes_basename = f"{slug}.md"
    run_log_name = f"{generated_at.strftime('%Y%m%d-%H%M%S')}-{_slugify(title)}.log"
    run_log_path = outputs_dir / run_log_name
    orchestration_log_path = logs_dir / "orchestration.log"

    project_links = {
        "readme": _repo_relative(factory_repo_root, project_root / "README.md"),
        "deploy": _repo_relative(factory_repo_root, project_root / "DEPLOY.md"),
        "diagram": _repo_relative(factory_repo_root, diagrams_dir / diagram_basename),
        "architectureOverview": _repo_relative(factory_repo_root, docs_dir / "architecture-overview.md"),
        "traceability": _repo_relative(factory_repo_root, docs_dir / "traceability-matrix.md"),
    }

    analysis = {
        "title": title,
        "projectSlug": slug,
        "generatedFrom": brd_path.name,
        "designChoice": "Azure-native in-repo BRD runner with generated starter deliverables.",
        "benefits": [
            "No dependency on sibling repositories for portal BRD processing.",
            "Deterministic project scaffolding inside the Azure Architecture Factory repo.",
            "Project feed, manifests, logs, and starter assets are generated in one place.",
        ],
        "alternativeConsidered": "Shelling out to a sibling repository pipeline was rejected because it is not portable to the hosted Azure deployment.",
        "status": "Ready",
    }

    _write_text(project_root / "README.md", _build_readme(title, brd_path.name, slug, requirements))
    _write_text(project_root / "DEPLOY.md", _build_deploy(slug))
    _write_text(docs_dir / "architecture-overview.md", _build_architecture_overview(title, requirements, capabilities))
    _write_text(docs_dir / "governance-model.md", _build_governance_model(capabilities))
    _write_text(docs_dir / "delivery-milestones.md", _build_delivery_milestones())
    _write_text(docs_dir / "success-criteria.md", _build_success_criteria(success_criteria))
    _write_text(docs_dir / "traceability-matrix.md", _build_traceability_matrix(requirements, success_criteria))
    _write_text(diagrams_dir / diagram_notes_basename, _build_diagram_notes(title, requirements, capabilities))
    _write_text(diagrams_dir / diagram_basename, _build_drawio(title))
    _write_text(src_dir / "__init__.py", "")
    _write_text(src_dir / "main.py", _build_api_main())
    _write_text(src_dir / "models.py", _build_api_models())
    _write_text(services_dir / "__init__.py", "")
    _write_text(services_dir / "copilot_service.py", _build_api_service())
    _write_text(project_root / "requirements.txt", "fastapi==0.116.1\nuvicorn[standard]==0.32.1\npydantic==2.10.3\n")
    _write_text(project_root / "pyproject.toml", _build_pyproject(title))
    _write_text(infra_dir / "main.bicep", _build_infra_bicep())
    _write_text(tests_dir / "test_generated_project.py", _build_test())
    user_home_copy_path = _copy_project_to_user_home(project_root, slug)

    manifest = {
        "project": slug,
        "status": "complete",
        "source_brd": str(brd_path),
        "created_at": generated_at_iso,
        "generator": "azure_native_factory_runner",
        "title": title,
        "requirements_detected": requirements,
        "success_criteria_detected": success_criteria,
        "capabilities": capabilities,
        "user_home_copy": str(user_home_copy_path),
    }
    _write_json(project_root / "project-manifest.json", manifest)

    orchestration_log = "\n".join([
        f"[{generated_at_iso}] [PHASE 0] project-manifest.json initialized",
        f"[{generated_at_iso}] [PHASE 1] BRD parsed from {brd_path.name}",
        f"[{generated_at_iso}] [PHASE 2] Starter project assets created under {slug}",
        f"[{generated_at_iso}] [PHASE 2A] Project copied to {user_home_copy_path}",
        f"[{generated_at_iso}] [PHASE 3] factory-projects.generated.json updated",
        f"[{generated_at_iso}] [FINAL] status=complete",
        "",
    ])
    _write_text(orchestration_log_path, orchestration_log)

    run_log = "\n".join([
        f"run_id={run_id}",
        f"generated_at={generated_at_iso}",
        f"project_slug={slug}",
        f"source_brd={brd_path.name}",
        f"user_home_copy={user_home_copy_path}",
        "status=complete",
        "runner=azure_native_factory_runner",
        "",
    ])
    _write_text(run_log_path, run_log)

    project_record = {
        "slug": slug,
        "title": title,
        "status": "Ready",
        "generatedFrom": brd_path.name,
        "generatedAt": generated_at_iso,
        "links": project_links,
        "runLog": f"outputs\\brd-runs\\{run_log_name}",
    }
    _update_project_feed(factory_repo_root / "factory-projects.generated.json", generated_at_iso, project_record)

    return {
        "status": "complete",
        "project": project_record,
        "analysis": analysis,
        "manifest": _repo_relative(factory_repo_root, project_root / "project-manifest.json"),
        "orchestrationLog": _repo_relative(factory_repo_root, orchestration_log_path),
        "userHomeCopy": str(user_home_copy_path),
    }


def _copy_project_to_user_home(project_root: Path, slug: str) -> Path:
    app_root = Path.home() / "app"
    app_root.mkdir(parents=True, exist_ok=True)
    destination = app_root / slug
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(project_root, destination)
    return destination


def _extract_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback.replace("-", " ").title()


def _extract_requirements(markdown: str) -> list[str]:
    requirements: list[str] = []
    section_name = ""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            section_name = stripped.lstrip("#").strip().lower()
            continue
        if stripped.startswith(("- ", "* ")):
            item = stripped[2:].strip()
            if item and ("require" in section_name or "scope" in section_name or "success" not in section_name):
                requirements.append(item)
    if not requirements:
        requirements = [
            line.strip()
            for line in markdown.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ][:8]
    return requirements or ["Business requirements captured from BRD input"]


def _extract_success_criteria(markdown: str) -> list[str]:
    criteria: list[str] = []
    in_section = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            in_section = "success" in stripped.lower()
            continue
        if in_section and stripped.startswith(("- ", "* ")):
            criteria.append(stripped[2:].strip())
    return criteria or ["Generated starter solution is reviewed and refined before production deployment"]


def _infer_capabilities(markdown: str) -> dict[str, bool]:
    lowered = markdown.lower()
    return {
        "openai": "openai" in lowered or "azure ai" in lowered,
        "copilot": "copilot" in lowered,
        "ml": "machine learning" in lowered or "ml" in lowered,
        "governance": any(term in lowered for term in ["governance", "policy", "compliance", "security"]),
        "workflow": any(term in lowered for term in ["workflow", "process", "approval", "orchestration"]),
        "api": any(term in lowered for term in ["api", "rest", "endpoint", "integration"]),
    }


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return normalized.strip("-") or "project"


def _repo_relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _update_project_feed(feed_path: Path, generated_at: str, project_record: dict[str, Any]) -> None:
    if feed_path.exists():
        payload = json.loads(feed_path.read_text(encoding="utf-8"))
    else:
        payload = {"generatedAt": None, "projects": []}

    existing = [project for project in payload.get("projects", []) if project.get("slug") != project_record["slug"]]
    payload["generatedAt"] = generated_at
    payload["projects"] = [project_record, *existing]
    _write_json(feed_path, payload)


def _build_readme(title: str, source_brd: str, slug: str, requirements: list[str]) -> str:
    highlights = "\n".join(f"- {item}" for item in requirements[:10])
    return f"# {title}\n\nGenerated from BRD `{source_brd}` by the Azure-native factory runner.\n\n## What Was Generated\n- `docs/architecture-overview.md`\n- `docs/governance-model.md`\n- `docs/delivery-milestones.md`\n- `docs/success-criteria.md`\n- `docs/traceability-matrix.md`\n- `diagrams/{slug}.md`\n- `diagrams/{slug}.drawio`\n- `src/copilot_api/main.py`\n- `src/copilot_api/models.py`\n- `src/copilot_api/services/copilot_service.py`\n- `requirements.txt`\n- `infra/main.bicep`\n- `tests/test_generated_project.py`\n\n## BRD Requirement Highlights\n{highlights}\n"


def _build_deploy(slug: str) -> str:
    return f"# Deploy\n\n## Prerequisites\n- Python 3.11+\n- Azure CLI authenticated\n- Target Azure subscription and resource group\n\n## Local Validation\n```bash\npython -m venv .venv\n.venv\\Scripts\\activate\npython -m pip install -r requirements.txt\npython -m pytest tests -q\n```\n\n## Local Run\n```bash\npython -m uvicorn src.copilot_api.main:app --host 127.0.0.1 --port 8000 --reload\n```\n\n## Azure Deployment Outline\n1. Review and customize `infra/main.bicep`.\n2. Provision hosting, identity, Key Vault access, and Application Insights.\n3. Configure application settings for the generated API.\n4. Deploy the project from `projects/{slug}`.\n5. Validate `/health` after deployment.\n"


def _build_architecture_overview(title: str, requirements: list[str], capabilities: dict[str, bool]) -> str:
    capability_lines = [
        f"- Azure OpenAI: {'Yes' if capabilities['openai'] else 'Not explicitly requested'}",
        f"- Microsoft Copilot: {'Yes' if capabilities['copilot'] else 'Not explicitly requested'}",
        f"- Machine Learning lifecycle: {'Yes' if capabilities['ml'] else 'Not explicitly requested'}",
        f"- Governance controls: {'Yes' if capabilities['governance'] else 'Baseline included'}",
    ]
    requirement_lines = "\n".join(f"- {item}" for item in requirements[:8])
    return f"# {title} - Architecture Overview\n\n## Target Architecture\nThis starter architecture packages the submitted BRD into a generated project scaffold that can be refined for Azure deployment.\n\n## Requirement Signals\n{requirement_lines}\n\n## Recommended Building Blocks\n- Presentation or workflow entry point\n- Integration API layer\n- Data or document store\n- Observability with Application Insights and Log Analytics\n- Identity, secrets, and governance controls\n\n## Capability Coverage\n" + "\n".join(capability_lines) + "\n"


def _build_governance_model(capabilities: dict[str, bool]) -> str:
    controls = [
        "- Managed identity for service-to-service authentication",
        "- Key Vault-backed secret management",
        "- Least-privilege RBAC for runtime and deployment identities",
        "- Application Insights and structured run logs for traceability",
    ]
    if capabilities["governance"]:
        controls.append("- Governance review checkpoint based on BRD security and compliance requirements")
    return "# AI/ML Governance Model\n\n## Governance Controls\n" + "\n".join(controls) + "\n\n## Operating Cadence\n- Review generated starter assets before production use\n- Track deployment changes through version control and manifest updates\n- Re-run BRD generation when requirements materially change\n"


def _build_delivery_milestones() -> str:
    return "# Delivery Milestones\n\n## Phase 1 - Intake and Architecture\n- Capture BRD inputs\n- Generate baseline project artifacts and architecture notes\n\n## Phase 2 - Application Refinement\n- Replace starter API implementation with workload-specific logic\n- Expand tests, infrastructure, and deployment automation\n\n## Phase 3 - Production Readiness\n- Harden security, networking, and observability\n- Validate deployment readiness and operational ownership\n"


def _build_success_criteria(success_criteria: list[str]) -> str:
    lines = "\n".join(f"- {item}" for item in success_criteria)
    return f"# Success Criteria\n\n## KPI Candidates\n{lines}\n\n## Measurement Approach\n- Establish a baseline before implementation\n- Track changes through test results, deployment validation, and user feedback\n- Assign an owner for each acceptance criterion\n"


def _build_traceability_matrix(requirements: list[str], success_criteria: list[str]) -> str:
    rows = ["| BRD Requirement | Generated Artifact | Validation Approach |", "|---|---|---|"]
    for requirement in requirements[:12]:
        rows.append(f"| {requirement.replace('|', '/')} | Architecture Overview, Deployment Guide, Starter API | Review generated artifacts and extend tests |")
    for criterion in success_criteria[:6]:
        rows.append(f"| Success: {criterion.replace('|', '/')} | Success Criteria document | Verify acceptance owner and validation evidence |")
    return "# Traceability Matrix\n\n" + "\n".join(rows) + "\n"


def _build_diagram_notes(title: str, requirements: list[str], capabilities: dict[str, bool]) -> str:
    return f"# {title} - Architecture Overview\n\n## Summary\nThis generated starter design maps the BRD into a simple Azure-oriented architecture shape.\n\n## Signals\n" + "\n".join(f"- {item}" for item in requirements[:8]) + "\n\n## Capability Flags\n" + "\n".join(f"- {name}: {'yes' if enabled else 'no'}" for name, enabled in capabilities.items()) + "\n"


def _build_drawio(title: str) -> str:
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<mxfile host=\"app.diagrams.net\" version=\"24.7.3\"><diagram id=\"arch1\" name=\"Architecture\"><mxGraphModel dx=\"1600\" dy=\"900\" grid=\"1\" gridSize=\"10\" guides=\"1\" tooltips=\"1\" connect=\"1\" arrows=\"1\" fold=\"1\" page=\"1\" pageScale=\"1\" pageWidth=\"1600\" pageHeight=\"1000\" math=\"0\" shadow=\"0\"><root><mxCell id=\"0\"/><mxCell id=\"1\" parent=\"0\"/><mxCell id=\"title\" value=\"{safe_title}\" style=\"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=24;fontStyle=1;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"80\" y=\"70\" width=\"1200\" height=\"40\" as=\"geometry\"/></mxCell><mxCell id=\"node1\" value=\"User Workflow\" style=\"rounded=1;whiteSpace=wrap;html=1;fillColor=#e7f3ff;strokeColor=#0078d4;fontColor=#0b2f4f;fontSize=12;spacing=6;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"80\" y=\"220\" width=\"220\" height=\"100\" as=\"geometry\"/></mxCell><mxCell id=\"node2\" value=\"API Layer\" style=\"rounded=1;whiteSpace=wrap;html=1;fillColor=#e7f3ff;strokeColor=#0078d4;fontColor=#0b2f4f;fontSize=12;spacing=6;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"380\" y=\"220\" width=\"220\" height=\"100\" as=\"geometry\"/></mxCell><mxCell id=\"node3\" value=\"Azure Data / Knowledge\" style=\"rounded=1;whiteSpace=wrap;html=1;fillColor=#e7f3ff;strokeColor=#0078d4;fontColor=#0b2f4f;fontSize=12;spacing=6;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"680\" y=\"220\" width=\"220\" height=\"100\" as=\"geometry\"/></mxCell><mxCell id=\"node4\" value=\"Observability / Governance\" style=\"rounded=1;whiteSpace=wrap;html=1;fillColor=#e7f3ff;strokeColor=#0078d4;fontColor=#0b2f4f;fontSize=12;spacing=6;\" vertex=\"1\" parent=\"1\"><mxGeometry x=\"980\" y=\"220\" width=\"260\" height=\"100\" as=\"geometry\"/></mxCell><mxCell id=\"edge1\" value=\"\" style=\"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#2a6ea8;endArrow=block;endFill=1;\" edge=\"1\" parent=\"1\" source=\"node1\" target=\"node2\"><mxGeometry relative=\"1\" as=\"geometry\"/></mxCell><mxCell id=\"edge2\" value=\"\" style=\"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#2a6ea8;endArrow=block;endFill=1;\" edge=\"1\" parent=\"1\" source=\"node2\" target=\"node3\"><mxGeometry relative=\"1\" as=\"geometry\"/></mxCell><mxCell id=\"edge3\" value=\"\" style=\"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#2a6ea8;endArrow=block;endFill=1;\" edge=\"1\" parent=\"1\" source=\"node3\" target=\"node4\"><mxGeometry relative=\"1\" as=\"geometry\"/></mxCell></root></mxGraphModel></diagram></mxfile>"


def _build_api_main() -> str:
    return "from datetime import datetime, timezone\nfrom fastapi import FastAPI\n\nfrom .models import AskRequest, AskResponse\nfrom .services.copilot_service import build_response\n\n\napp = FastAPI(title=\"Generated Copilot API\", version=\"0.1.0\")\n\n\n@app.get(\"/health\")\ndef health() -> dict:\n    return {\"status\": \"ok\", \"timestamp\": datetime.now(timezone.utc).isoformat()}\n\n\n@app.post(\"/api/copilot/ask\", response_model=AskResponse)\ndef ask_copilot(payload: AskRequest) -> AskResponse:\n    return AskResponse(answer=build_response(payload.question, payload.context), source=\"generated-starter\")\n"


def _build_api_models() -> str:
    return "from pydantic import BaseModel, Field\n\n\nclass AskRequest(BaseModel):\n    question: str = Field(min_length=3)\n    context: str = Field(default=\"\")\n\n\nclass AskResponse(BaseModel):\n    answer: str\n    source: str\n"


def _build_api_service() -> str:
    return "def build_response(question: str, context: str) -> str:\n    summary = context.strip()[:240]\n    if summary:\n        return \"Starter copilot response for question: '\" + question + \"'. Context summary: \" + summary + \". Replace this logic with your workload-specific orchestration.\"\n    return \"Starter copilot response for question: '\" + question + \"'. Replace this logic with your workload-specific orchestration.\"\n"


def _build_pyproject(title: str) -> str:
    normalized = _slugify(title).replace("-", "_")
    return f"[project]\nname = \"{normalized}\"\nversion = \"0.1.0\"\ndescription = \"Generated starter project for {title}\"\nrequires-python = \">=3.11\"\ndependencies = [\n  \"fastapi==0.116.1\",\n  \"uvicorn[standard]==0.32.1\",\n  \"pydantic==2.10.3\",\n]\n"


def _build_infra_bicep() -> str:
    return "targetScope = 'resourceGroup'\n\n@description('Deployment location')\nparam location string = resourceGroup().location\n\n@description('Environment name')\nparam environment string = 'dev'\n\noutput deploymentHint string = 'Replace this starter Bicep file with workload-specific Azure resources.'\noutput locationUsed string = location\noutput environmentName string = environment\n"


def _build_test() -> str:
    return "from pathlib import Path\n\n\ndef test_generated_project_docs_exist():\n    root = Path(__file__).resolve().parents[1]\n    required = [\n        root / 'README.md',\n        root / 'DEPLOY.md',\n        root / 'requirements.txt',\n        root / 'src' / 'copilot_api' / 'main.py',\n        root / 'src' / 'copilot_api' / 'models.py',\n        root / 'src' / 'copilot_api' / 'services' / 'copilot_service.py',\n        root / 'docs' / 'architecture-overview.md',\n        root / 'docs' / 'governance-model.md',\n        root / 'docs' / 'delivery-milestones.md',\n        root / 'docs' / 'success-criteria.md',\n        root / 'docs' / 'traceability-matrix.md',\n        root / 'diagrams' / (root.name + '.md'),\n        root / 'project-manifest.json',\n    ]\n    missing = [str(path) for path in required if not path.exists()]\n    assert not missing, f'Missing generated docs: {missing}'\n"