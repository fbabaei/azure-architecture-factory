#!/usr/bin/env python
"""
Azure Architecture Factory - Interactive Demo Application

A web-based showcase demonstrating the end-to-end automation capabilities
of the Azure Architecture Factory platform.
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parent
ORDER_MONITORING_FILE = REPO_ROOT / "projects" / "order-management-platform" / "monitoring-dashboard.html"
ORDER_MGMT_ROOT = REPO_ROOT / "projects" / "order-management-platform"
STORAGE_SELF_SERVICE_ROOT = REPO_ROOT / "projects" / "storage-self-service-provisioning"
FABRIC_MEDALLION_ROOT = REPO_ROOT / "projects" / "fabric-medallion-pipeline"

FACTORY_PROJECTS = [
    {
        "id": "order-management-platform",
        "name": "Order Management Platform",
        "description": "End-to-end microservices output with diagrams, code, infra, docs, tests, deployment guide, and readiness scoring.",
        "kind": "Microservices",
        "path": ORDER_MGMT_ROOT,
        "test_command": "python -m pytest tests/unit tests/integration -v --tb=short --no-header",
    },
    {
        "id": "storage-self-service-provisioning",
        "name": "Storage Self-Service Provisioning",
        "description": "Service-oriented implementation with API, worker, shared libraries, docs, and a runnable unittest suite.",
        "kind": "Workflow Service",
        "path": STORAGE_SELF_SERVICE_ROOT,
        "test_command": "python -m unittest discover tests",
    },
    {
        "id": "aks-microservices-demo",
        "name": "AKS Microservices Demo",
        "description": "Platform-oriented AKS example with infrastructure, Kubernetes manifests, scripts, and service scaffolding.",
        "kind": "AKS Platform",
        "path": REPO_ROOT / "projects" / "aks-microservices-demo",
        "test_command": None,
    },
    {
        "id": "ecommerce-demo",
        "name": "E-Commerce Demo",
        "description": "Frontend-oriented sample showing lightweight generated deliverables and a web-facing experience.",
        "kind": "Web App",
        "path": REPO_ROOT / "projects" / "ecommerce-demo",
        "test_command": None,
    },
    {
        "id": "fabric-medallion-pipeline",
        "name": "Fabric Medallion Pipeline",
        "description": "Data pipeline sample with Bronze, Silver, and Gold stages, governance helpers, Bicep infrastructure, and a runnable test suite.",
        "kind": "Data Pipeline",
        "path": FABRIC_MEDALLION_ROOT,
        "test_command": "python -m pytest tests -v --tb=short --no-header",
    },
]


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []

    records = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _get_python_executable() -> str:
    venv_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _run_command(command: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _count_service_folders(src_path: Path) -> int:
    if not src_path.exists():
        return 0

    ignored_names = {
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "shared-lib",
        "shared_lib",
        "web",
        "static",
    }
    return sum(
        1
        for child in src_path.iterdir()
        if child.is_dir() and child.name not in ignored_names
    )


def _detect_project_artifacts(project: dict) -> dict:
    project_root = project["path"]
    diagrams_path = project_root / "diagrams"
    src_path = project_root / "src"
    docs_path = project_root / "docs"
    tests_path = project_root / "tests"
    infra_path = project_root / "infra"
    manifest_path = project_root / "project-manifest.json"
    manifest = _read_json(manifest_path)

    has_diagram = diagrams_path.exists() and any(diagrams_path.glob("*.drawio"))
    has_notes = diagrams_path.exists() and any(diagrams_path.glob("*.md"))
    has_src = src_path.exists() and any(src_path.iterdir())
    has_docs = docs_path.exists() and any(docs_path.iterdir())
    has_tests = tests_path.exists() and any(tests_path.iterdir())
    has_infra = infra_path.exists() and any(infra_path.iterdir())
    has_readme = (project_root / "README.md").exists()
    has_deploy = (project_root / "DEPLOY.md").exists()
    has_manifest = manifest is not None
    service_count = _count_service_folders(src_path)

    full_lifecycle_evidence = all([has_diagram, has_notes, has_src, has_docs, has_tests])
    production_like = full_lifecycle_evidence and has_infra and has_readme

    readiness_status = None
    readiness_score = None
    if manifest:
        readiness_status = manifest.get("deployment_readiness", {}).get("status")
        readiness_score = manifest.get("phases", {}).get("4_production_review", {}).get("readiness_score")

    evidence = []
    if has_diagram:
        evidence.append("Architecture diagram")
    if has_notes:
        evidence.append("Architecture notes")
    if has_src:
        evidence.append(f"Source structure ({service_count} service folders)")
    if has_docs:
        evidence.append("Project docs")
    if has_tests:
        evidence.append("Tests")
    if has_infra:
        evidence.append("Infrastructure")
    if has_deploy:
        evidence.append("Deployment guide")
    if readiness_status:
        evidence.append(readiness_status)

    return {
        "id": project["id"],
        "name": project["name"],
        "description": project["description"],
        "kind": project["kind"],
        "path": _repo_relative(project_root),
        "test_command": project["test_command"],
        "service_count": service_count,
        "has_diagram": has_diagram,
        "has_notes": has_notes,
        "has_src": has_src,
        "has_docs": has_docs,
        "has_tests": has_tests,
        "has_infra": has_infra,
        "has_readme": has_readme,
        "has_deploy": has_deploy,
        "has_manifest": has_manifest,
        "full_lifecycle_evidence": full_lifecycle_evidence,
        "production_like": production_like,
        "readiness_status": readiness_status,
        "readiness_score": readiness_score,
        "evidence": evidence,
    }


def _build_factory_readiness_payload() -> dict:
    projects = [_detect_project_artifacts(project) for project in FACTORY_PROJECTS]
    testable_projects = [project for project in projects if project["test_command"]]

    full_lifecycle_count = sum(1 for project in projects if project["full_lifecycle_evidence"])
    production_like_count = sum(1 for project in projects if project["production_like"])
    if production_like_count == len(projects):
        assessment = "All tracked sample outputs currently show production-like evidence with architecture, code, docs, tests, and infrastructure."
    elif full_lifecycle_count == len(projects):
        assessment = "All tracked sample outputs now provide full lifecycle evidence; a subset still needs infrastructure hardening to be fully production-like."
    else:
        assessment = "The repository demonstrates a credible BRD-to-project factory, but only a subset of sample outputs currently show the full production-style chain of diagram, code, docs, tests, and infrastructure."

    summary = {
        "project_count": len(projects),
        "full_lifecycle_count": full_lifecycle_count,
        "production_like_count": production_like_count,
        "testable_project_count": len(testable_projects),
        "diagram_count": sum(1 for project in projects if project["has_diagram"]),
        "source_count": sum(1 for project in projects if project["has_src"]),
        "docs_count": sum(1 for project in projects if project["has_docs"]),
        "tests_count": sum(1 for project in projects if project["has_tests"]),
        "infra_count": sum(1 for project in projects if project["has_infra"]),
        "assessment": assessment,
        "strongest_evidence": "order-management-platform",
    }

    return {
        "updated_at": datetime.now().isoformat(),
        "summary": summary,
        "projects": projects,
    }


def _run_order_management_tests_internal() -> dict:
    test_dir = ORDER_MGMT_ROOT / "tests"
    if not test_dir.exists():
        return {"status": "error", "message": f"Tests directory not found: {test_dir}"}

    process = _run_command(
        [_get_python_executable(), "-m", "pytest", "tests/unit", "tests/integration", "-v", "--tb=short", "--no-header"],
        ORDER_MGMT_ROOT,
    )

    output = process.stdout + ("\n" + process.stderr if process.stderr.strip() else "")
    tests = []
    passed = 0
    failed = 0
    errors = 0

    for line in output.splitlines():
        for marker in ("PASSED", "FAILED", "ERROR"):
            if f" {marker}" in line:
                name = line.split(" " + marker)[0].strip()
                if "::" in name:
                    name = name.split("/")[-1]
                tests.append({"name": name, "result": marker})
                if marker == "PASSED":
                    passed += 1
                elif marker == "FAILED":
                    failed += 1
                else:
                    errors += 1
                break

    summary = ""
    for line in reversed(output.splitlines()):
        stripped = line.strip().lstrip("= ").rstrip("= ").strip()
        if stripped and ("passed" in stripped or "failed" in stripped or "error" in stripped):
            summary = stripped
            break

    return {
        "project": "order-management-platform",
        "status": "success" if process.returncode == 0 else "failed",
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": passed + failed + errors,
        "summary": summary,
        "tests": tests,
        "output": output[-8000:],
        "exit_code": process.returncode,
        "ran_at": datetime.now().isoformat(),
    }


def _run_storage_self_service_tests_internal() -> dict:
    test_dir = STORAGE_SELF_SERVICE_ROOT / "tests"
    if not test_dir.exists():
        return {"project": "storage-self-service-provisioning", "status": "error", "message": f"Tests directory not found: {test_dir}"}

    process = _run_command(
        [_get_python_executable(), "-m", "unittest", "discover", "tests"],
        STORAGE_SELF_SERVICE_ROOT,
    )
    output = process.stdout + ("\n" + process.stderr if process.stderr.strip() else "")
    summary = "OK" if process.returncode == 0 else "FAILED"

    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped.startswith("Ran ") or stripped == "OK" or stripped.startswith("FAILED"):
            summary = stripped
            break

    return {
        "project": "storage-self-service-provisioning",
        "status": "success" if process.returncode == 0 else "failed",
        "summary": summary,
        "output": output[-6000:],
        "exit_code": process.returncode,
        "ran_at": datetime.now().isoformat(),
    }


def _run_fabric_medallion_tests_internal() -> dict:
    test_dir = FABRIC_MEDALLION_ROOT / "tests"
    if not test_dir.exists():
        return {"project": "fabric-medallion-pipeline", "status": "error", "message": f"Tests directory not found: {test_dir}"}

    process = _run_command(
        [_get_python_executable(), "-m", "pytest", "tests", "-v", "--tb=short", "--no-header"],
        FABRIC_MEDALLION_ROOT,
    )
    output = process.stdout + ("\n" + process.stderr if process.stderr.strip() else "")

    passed = 0
    failed = 0
    errors = 0
    for line in output.splitlines():
        for marker in ("PASSED", "FAILED", "ERROR"):
            if f" {marker}" in line:
                if marker == "PASSED":
                    passed += 1
                elif marker == "FAILED":
                    failed += 1
                else:
                    errors += 1
                break

    summary = ""
    for line in reversed(output.splitlines()):
        stripped = line.strip().lstrip("= ").rstrip("= ").strip()
        if stripped and ("passed" in stripped or "failed" in stripped or "error" in stripped):
            summary = stripped
            break

    return {
        "project": "fabric-medallion-pipeline",
        "status": "success" if process.returncode == 0 else "failed",
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": passed + failed + errors,
        "summary": summary,
        "output": output[-8000:],
        "exit_code": process.returncode,
        "ran_at": datetime.now().isoformat(),
    }

# Demo data
DEMO_SCENARIOS = {
    "ecommerce": {
        "name": "E-Commerce Platform",
        "description": "Multi-tenant SaaS platform with real-time inventory, orders, and analytics",
        "industry": "Retail",
        "complexity": "Advanced",
        "services": ["Web Apps", "Cosmos DB", "Event Hubs", "Azure AI Search", "App Insights"],
        "timeline": "3 hours to deployment"
    },
    "data_pipeline": {
        "name": "Data & Analytics Platform",
        "description": "Multi-stage analytics platform with ingestion, transformation, governance, and semantic outputs",
        "industry": "Financial Services",
        "complexity": "Advanced",
        "services": ["Azure Data Lake", "Data Factory", "Fabric", "Synapse", "Power BI"],
        "timeline": "2 hours to deployment"
    },
    "microservices": {
        "name": "Microservices Architecture",
        "description": "Containerized microservices with async messaging and orchestration",
        "industry": "Technology",
        "complexity": "Advanced",
        "services": ["Container Apps", "Service Bus", "API Management", "Key Vault", "Monitor"],
        "timeline": "2.5 hours to deployment"
    },
    "generative_ai": {
        "name": "Generative AI Application",
        "description": "Chat application with retrieval augmented generation (RAG)",
        "industry": "Enterprise Software",
        "complexity": "Advanced",
        "services": ["Azure OpenAI", "AI Search", "Cosmos DB", "App Service", "Monitor"],
        "timeline": "1.5 hours to deployment"
    },
    "aks_microservices": {
        "name": "AKS Microservice Platform",
        "description": "Kubernetes-based microservice architecture with GitOps and platform guardrails",
        "industry": "Technology",
        "complexity": "Advanced",
        "services": ["AKS", "Azure Container Registry", "Application Gateway", "Azure Monitor", "Key Vault"],
        "timeline": "3.5 hours to deployment"
    },
}

AGENT_PHASES = [
    {
        "phase": 0,
        "agent": "project-state-manager",
        "task": "Isolated project folder setup",
        "duration": "< 1 min",
        "output": "Project manifest, folder structure"
    },
    {
        "phase": 1,
        "agent": "brd-to-architecture-diagram",
        "task": "Convert requirements to diagram",
        "duration": "2-3 min",
        "output": "Draw.io architecture diagram"
    },
    {
        "phase": 2,
        "agent": "azure-architecture-implementer",
        "task": "Scaffold services and modules",
        "duration": "3-5 min",
        "output": "Python microservices, shared libraries"
    },
    {
        "phase": 3,
        "agent": "bicep-infrastructure-validator",
        "task": "Generate and validate IaC",
        "duration": "4-6 min",
        "output": "Bicep modules, multi-environment params"
    },
    {
        "phase": 4,
        "agent": "production-environment-advisor",
        "task": "Production readiness review",
        "duration": "2-3 min",
        "output": "Prerequisites checklist, DEPLOY.md"
    },
    {
        "phase": 5,
        "agent": "azure-project-deployer",
        "task": "One-command Azure deployment",
        "duration": "8-12 min",
        "output": "Deployed services, live endpoints"
    }
]

BENEFITS = [
    {
        "title": "90% Faster Time-to-Deployment",
        "description": "From 4-8 weeks to hours. Requirements → Architecture → Code → Infrastructure → Deployed.",
        "metric": "3-4 hours vs 4-8 weeks",
        "icon": "⚡"
    },
    {
        "title": "Zero Manual Handoffs",
        "description": "AI-driven agent orchestration automates the full lifecycle. No architect → developer → DevOps → operations chain.",
        "metric": "100% automated workflow",
        "icon": "🤖"
    },
    {
        "title": "Self-Healing Infrastructure Code",
        "description": "Bicep validation auto-detects and fixes syntax, logic, and configuration errors before deployment.",
        "metric": "0 deployment failures from IaC",
        "icon": "🛡️"
    },
    {
        "title": "Standardized Project Structure",
        "description": "Every project gets the same folder structure, documentation, tests, and infrastructure layout.",
        "metric": "100% consistency",
        "icon": "📋"
    },
    {
        "title": "Production-Ready Code",
        "description": "Scaffolded services include observability, resilience, governance, and security patterns by default.",
        "metric": "Enterprise-grade baseline",
        "icon": "🏅"
    },
    {
        "title": "Reference Implementation Included",
        "description": "Repository includes multiple sample outputs spanning microservices, workflow automation, AKS, and web app scenarios.",
        "metric": "Multi-project evidence",
        "icon": "📦"
    }
]

def _build_demo_metrics() -> dict:
    readiness = _build_factory_readiness_payload()
    summary = readiness["summary"]
    return {
        "project_count": summary["project_count"],
        "full_lifecycle_count": summary["full_lifecycle_count"],
        "production_like_count": summary["production_like_count"],
        "testable_project_count": summary["testable_project_count"],
        "updated_at": readiness["updated_at"],
    }

AKS_DEMO = {
    "title": "AKS Microservice Design Demo",
    "summary": "A production-oriented AKS blueprint generated with Azure Architecture Factory conventions.",
    "service_boundary": [
        "Edge Layer: Azure Application Gateway + WAF (ingress)",
        "Workload Layer: AKS namespaces for core-api, catalog, ordering, and payments",
        "Data Layer: Azure Database for PostgreSQL + Azure Cache for Redis",
        "Platform Layer: Azure Container Registry, Key Vault, Azure Monitor, and Log Analytics",
    ],
    "delivery_flow": [
        "Phase 0: project-state-manager initializes project folder and manifests",
        "Phase 1: brd-to-architecture-diagram generates AKS-centric architecture",
        "Phase 2: azure-architecture-implementer scaffolds services and shared libraries",
        "Phase 3: bicep-infrastructure-validator emits AKS/network/security modules",
        "Phase 4: production-environment-advisor validates readiness and operations",
        "Phase 5: azure-project-deployer executes deployment with captured outputs",
    ],
    "azure_resources": [
        "Azure Kubernetes Service (private cluster optional)",
        "Azure Container Registry with image pull via managed identity",
        "Application Gateway Ingress Controller (AGIC)",
        "Azure Key Vault CSI driver for secret injection",
        "Azure Monitor Container Insights + Application Insights",
        "Log Analytics workspace and alert rules",
    ],
    "deployment_endpoints": [
        {"name": "API Gateway", "url": "https://aks-api.contoso.example"},
        {"name": "Operations Dashboard", "url": "https://portal.azure.com/#view/HubsExtension/BrowseResource/resourceType/microsoft.containerservice%2Fmanagedclusters"},
        {"name": "Grafana (optional)", "url": "https://grafana.contoso.example"},
    ],
    "security_controls": [
        "Workload identity for pod-to-Azure access",
        "Network policies + namespace isolation",
        "Ingress WAF policy and TLS termination",
        "Least-privilege RBAC and Key Vault secret references",
    ],
}

BRD_SCORECARD_ITEMS = [
    {"section": "Scope", "label": "Primary business outcome is explicit", "weight": 2},
    {"section": "Scope", "label": "Main users, systems, or personas are identified", "weight": 2},
    {"section": "Scope", "label": "Core capabilities are bounded and specific", "weight": 2},
    {"section": "Scope", "label": "Success criteria are stated", "weight": 1},
    {"section": "Workload Shape", "label": "Target workload type is recognizable", "weight": 2},
    {"section": "Workload Shape", "label": "Interaction model is clear", "weight": 2},
    {"section": "Workload Shape", "label": "Service boundaries or domains can be inferred", "weight": 2},
    {"section": "Workload Shape", "label": "Request is not a vague combination of unrelated systems", "weight": 1},
    {"section": "Azure Fit", "label": "Azure is explicitly required or clearly acceptable", "weight": 3},
    {"section": "Azure Fit", "label": "Hosting model maps to Azure services", "weight": 3},
    {"section": "Azure Fit", "label": "Required integrations are Azure-compatible", "weight": 3},
    {"section": "Azure Fit", "label": "No hard dependency contradicts Azure-first delivery", "weight": 3},
    {"section": "Data", "label": "Main data entities or documents are named", "weight": 2},
    {"section": "Data", "label": "Inputs and outputs are identified", "weight": 2},
    {"section": "Data", "label": "External integrations are described", "weight": 2},
    {"section": "Data", "label": "Data sensitivity or classification is mentioned", "weight": 2},
    {"section": "NFRs", "label": "Security expectations are stated", "weight": 3},
    {"section": "NFRs", "label": "Availability or resiliency expectations are stated", "weight": 2},
    {"section": "NFRs", "label": "Monitoring or operational visibility is expected", "weight": 2},
    {"section": "NFRs", "label": "Environment expectations are stated", "weight": 2},
    {"section": "Delivery Readiness", "label": "Enough detail exists to create a diagram", "weight": 2},
    {"section": "Delivery Readiness", "label": "Enough detail exists to scaffold source structure", "weight": 2},
    {"section": "Delivery Readiness", "label": "Enough detail exists to generate infra assumptions", "weight": 2},
    {"section": "Delivery Readiness", "label": "Enough detail exists to derive testable paths", "weight": 2},
]

BRD_SCORECARD_MAX = sum(item["weight"] * 2 for item in BRD_SCORECARD_ITEMS)

PROJECT_LINKS = [
    {
        "id": "factory-readiness",
        "name": "Factory Readiness Dashboard",
        "description": "Developer-facing evidence that shows which sample projects contain architecture, code, docs, tests, and infrastructure.",
        "environment": "Embedded in main demo",
        "url": "/factory-readiness",
        "cta": "Open Readiness",
        "kind": "Readiness",
        "external": False,
        "status_mode": "internal",
    },
    {
        "id": "order-management",
        "name": "Order Management Platform",
        "description": "Monitoring and test run view for the microservices platform.",
        "environment": "Embedded in main demo",
        "url": "/order-monitoring-dashboard",
        "cta": "Open Monitoring",
        "kind": "Monitoring",
        "external": False,
        "status_mode": "internal",
    },
    {
        "id": "aks-microservices",
        "name": "AKS Microservice Demo",
        "description": "Architecture and deployment blueprint for AKS-based microservices.",
        "environment": "Embedded in main demo",
        "url": "/aks-microservices-demo",
        "cta": "Open AKS Demo",
        "kind": "Architecture",
        "external": False,
        "status_mode": "internal",
    },
    {
        "id": "ecommerce-demo",
        "name": "E-Commerce Demo",
        "description": "Local storefront and API demo application.",
        "environment": "Local app on port 5001",
        "url": "http://localhost:5001/",
        "cta": "Open Storefront",
        "kind": "App",
        "external": True,
        "status_mode": "healthcheck",
        "health_url": "http://127.0.0.1:5001/health",
    },
    {
        "id": "storage-self-service",
        "name": "Storage Self-Service Provisioning",
        "description": "Local FastAPI provisioning service docs when the API is started.",
        "environment": "Expected local API docs on port 8000",
        "url": "http://localhost:8000/docs",
        "cta": "Open API Docs",
        "kind": "API",
        "external": True,
        "status_mode": "healthcheck",
        "health_url": "http://127.0.0.1:8000/health",
    },
    {
        "id": "fabric-medallion",
        "name": "Fabric Medallion Pipeline",
        "description": "Sample data-pipeline project page with architecture, artifacts, and validation entry points.",
        "environment": "Embedded in main demo",
        "url": "/fabric-medallion-pipeline",
        "cta": "Open Project",
        "kind": "Project",
        "external": False,
        "status_mode": "internal",
    },
]


def _probe_url(url: str, timeout: float = 1.5) -> tuple[bool, int | None]:
    request_obj = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(request_obj, timeout=timeout) as response:
            status_code = getattr(response, 'status', None) or response.getcode()
            return 200 <= status_code < 400, status_code
    except urllib.error.HTTPError as error:
        return False, error.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, None


def _get_project_link_statuses() -> list[dict]:
    statuses = []
    for project in PROJECT_LINKS:
        if project.get('status_mode') == 'internal':
            running = True
            status_code = 200
            state = 'running'
        else:
            running, status_code = _probe_url(project['health_url'])
            state = 'running' if running else 'offline'

        statuses.append({
            'id': project['id'],
            'name': project['name'],
            'url': project['url'],
            'cta': project['cta'],
            'external': project['external'],
            'running': running,
            'state': state,
            'status_code': status_code,
        })
    return statuses

@app.route('/')
def index():
    """Main demo page"""
    return render_template(
        'index.html',
        scenarios=DEMO_SCENARIOS,
        benefits=BENEFITS,
        metrics=_build_demo_metrics(),
        project_links=PROJECT_LINKS,
    )

@app.route('/api/scenarios')
def get_scenarios():
    """Get all demo scenarios"""
    return jsonify(list(DEMO_SCENARIOS.values()))


@app.route('/api/project-link-status')
def get_project_link_status():
    """Return current runtime status for project launch links."""
    statuses = _get_project_link_statuses()
    return jsonify({
        'updated_at': datetime.now().isoformat(),
        'projects': statuses,
    })

@app.route('/api/scenario/<scenario_id>')
def get_scenario(scenario_id):
    """Get details for a specific scenario"""
    if scenario_id in DEMO_SCENARIOS:
        return jsonify(DEMO_SCENARIOS[scenario_id])
    return jsonify({"error": "Scenario not found"}), 404

@app.route('/api/workflow')
def get_workflow():
    """Get agent orchestration workflow"""
    return jsonify({
        "phases": AGENT_PHASES,
        "total_time": "15-20 minutes",
        "stages": 6
    })

@app.route('/api/simulate-deployment', methods=['POST'])
def simulate_deployment():
    """Simulate a deployment process"""
    data = request.json
    scenario = data.get('scenario', 'ecommerce')
    
    # Simulate the workflow progression
    workflow = []
    for phase in AGENT_PHASES:
        workflow.append({
            **phase,
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        })
    
    return jsonify({
        "scenario": scenario,
        "workflow": workflow,
        "deployment_id": f"deploy-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "endpoints": [
            {"name": "Web App", "url": "https://app-ecommerce.azurewebsites.net"},
            {"name": "API Gateway", "url": "https://api-ecommerce.azure-api.net"},
            {"name": "Monitoring", "url": "https://insights.azure.com/..."}
        ],
        "status": "deployment_complete"
    })


@app.route('/api/aks/simulate-deployment', methods=['POST'])
def simulate_aks_deployment():
    """Simulate an AKS microservice deployment timeline."""
    phases = [
        {"name": "Cluster Baseline", "details": "Create AKS node pools, identity, and network profile.", "duration_seconds": 45},
        {"name": "Platform Add-ons", "details": "Enable ingress, CSI drivers, and observability agents.", "duration_seconds": 35},
        {"name": "Registry & Pull", "details": "Publish and validate microservice images from ACR.", "duration_seconds": 30},
        {"name": "Workload Release", "details": "Deploy namespaces, services, HPAs, and ingress rules.", "duration_seconds": 40},
        {"name": "Policy & Security", "details": "Apply network policies, workload identity, and Key Vault refs.", "duration_seconds": 30},
        {"name": "Smoke Tests", "details": "Run health checks and baseline synthetic transactions.", "duration_seconds": 20},
    ]

    return jsonify({
        "status": "deployment_complete",
        "deployment_id": f"aks-deploy-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "started_at": datetime.now().isoformat(),
        "timeline": phases,
        "endpoints": AKS_DEMO["deployment_endpoints"],
        "summary": "AKS platform and microservices released successfully in simulation mode.",
    })

@app.route('/api/project-structure')
def get_project_structure():
    """Get the generated project structure"""
    return jsonify({
        "root": "projects/my-platform",
        "folders": {
            "diagrams": {
                "description": "Architecture diagrams (Draw.io)",
                "files": ["platform-architecture.drawio", "platform-architecture.md"]
            },
            "src": {
                "description": "Microservices",
                "folders": ["service-1", "service-2", "shared-lib"]
            },
            "infra": {
                "description": "Bicep infrastructure (multi-environment)",
                "files": ["main.bicep", "params/dev.bicepparam", "params/prod.bicepparam"]
            },
            "tests": {
                "description": "Integration and unit tests",
                "files": ["test_service.py", "test_integration.py"]
            },
            "docs": {
                "description": "Project documentation",
                "files": ["README.md", "ARCHITECTURE.md", "DEPLOY.md"]
            }
        }
    })


@app.route('/api/factory-readiness')
def get_factory_readiness():
    """Summarize whether the repository shows full factory outputs across sample projects."""
    return jsonify(_build_factory_readiness_payload())


@app.route('/api/run-factory-validation', methods=['POST'])
def run_factory_validation():
    """Run the repository's representative validation suites and return an aggregate result."""
    order_results = _run_order_management_tests_internal()
    storage_results = _run_storage_self_service_tests_internal()
    medallion_results = _run_fabric_medallion_tests_internal()

    suites = [order_results, storage_results, medallion_results]
    passing = sum(1 for suite in suites if suite.get("status") == "success")
    failing = sum(1 for suite in suites if suite.get("status") not in {"success", "skipped"})

    return jsonify({
        "status": "success" if failing == 0 else "failed",
        "ran_at": datetime.now().isoformat(),
        "passing_suites": passing,
        "total_suites": len(suites),
        "suites": suites,
    })

@app.route('/presentation')
def presentation():
    """Leadership presentation page"""
    return render_template('presentation.html')


@app.route('/factory-readiness')
def factory_readiness_dashboard():
    """Developer-facing dashboard that summarizes factory output quality."""
    return render_template('factory_readiness_dashboard.html')


@app.route('/brd-readiness')
def brd_readiness_dashboard():
    """Interactive BRD readiness scorecard for portal users."""
    return render_template(
        'brd_readiness_dashboard.html',
        scorecard_items=BRD_SCORECARD_ITEMS,
        scorecard_max=BRD_SCORECARD_MAX,
    )


@app.route('/fabric-medallion-pipeline')
def fabric_medallion_pipeline():
    """Project summary page for the restored Fabric Medallion sample."""
    return render_template('fabric_medallion_pipeline.html')


@app.route('/aks-microservices-demo')
def aks_microservices_demo():
    """AKS microservice design demo page."""
    return render_template('aks_microservices_demo.html', aks_demo=AKS_DEMO)


@app.route('/api/run-order-management', methods=['POST'])
def run_order_management():
    """Run the order management platform tests and return structured results."""
    result = _run_order_management_tests_internal()
    if result.get("status") == "error":
        return jsonify(result), 404
    return jsonify(result)


@app.route('/order-monitoring-dashboard')
def order_monitoring_dashboard():
    """Wrapper page for Order Management monitoring dashboard."""
    return render_template('order_monitoring_dashboard.html')


@app.route('/order-monitoring-dashboard/raw')
def order_monitoring_dashboard_raw():
    """Serve the generated Order Management monitoring HTML."""
    if not ORDER_MONITORING_FILE.exists():
        return jsonify({
            "status": "error",
            "message": f"Monitoring dashboard not found: {ORDER_MONITORING_FILE}",
        }), 404

    return send_file(ORDER_MONITORING_FILE)

@app.route('/api/presentation-data')
def get_presentation_data():
    """Get presentation data for slides"""
    readiness = _build_factory_readiness_payload()
    summary = readiness["summary"]

    return jsonify({
        "title": "Azure Architecture Factory",
        "subtitle": "AI-Driven Architecture to Production Automation",
        "slides": [
            {
                "number": 1,
                "title": "The Problem",
                "content": "Requirements to Production Takes Weeks",
                "metrics": [
                    "4-8 weeks from BRD to deployed infrastructure",
                    "Manual handoffs between architects, developers, DevOps",
                    "Infrastructure errors discovered at deployment time",
                    "Inconsistent project structures across teams",
                    "No standardized governance or reliability patterns"
                ]
            },
            {
                "number": 2,
                "title": "Business Impact",
                "content": "Time-to-Market & Cost Implications",
                "metrics": [
                    "Delayed product launches cost market share",
                    "Manual processes introduce errors and delays",
                    "Teams spend 60-70% on infrastructure plumbing",
                    "Deployment failures increase operational costs",
                    "Inconsistency creates technical debt"
                ]
            },
            {
                "number": 3,
                "title": "The Solution",
                "content": "Azure Architecture Factory: Requirements to Production in Hours",
                "metrics": [
                    "AI-driven agent orchestration (6 phases)",
                    "Architecture diagrams generated from requirements",
                    "Microservices scaffolded and ready to customize",
                    "Bicep infrastructure generated and self-validated",
                    "One-command deployment to Azure"
                ]
            },
            {
                "number": 4,
                "title": "How It Works",
                "content": "6-Phase Automated Workflow",
                "metrics": [
                    "Phase 0: Project initialization (< 1 min)",
                    "Phase 1: Architecture diagram generation (2-3 min)",
                    "Phase 2: Service scaffolding (3-5 min)",
                    "Phase 3: Infrastructure code generation & validation (4-6 min)",
                    "Phase 4: Production readiness review (2-3 min)",
                    "Phase 5: Deployment to Azure (8-12 min)"
                ]
            },
            {
                "number": 5,
                "title": "Proven Results",
                "content": "Real Deployment Metrics",
                "metrics": [
                    f"{summary['project_count']} sample projects are currently evaluated in the readiness dashboard",
                    f"{summary['full_lifecycle_count']} projects currently show full lifecycle evidence (diagram, notes, source, docs, tests)",
                    f"{summary['production_like_count']} projects currently include production-like evidence (full lifecycle + infrastructure + root README)",
                    f"{summary['testable_project_count']} representative validation suites are wired into the portal",
                    f"Strongest baseline evidence: {summary['strongest_evidence']}",
                    f"Latest evidence refresh timestamp: {readiness['updated_at']}"
                ]
            },
            {
                "number": 6,
                "title": "Key Benefits",
                "content": "Quantified Value Proposition",
                "metrics": [
                    "⚡ 90% faster time-to-deployment (hours vs weeks)",
                    "🤖 100% automated workflow (zero manual handoffs)",
                    "🛡️ Self-healing infrastructure (0 deployment failures from IaC)",
                    "📋 100% standardization (consistent project structure)",
                    "🏅 Enterprise-grade baseline (observability, resilience, governance)",
                    "📦 Multiple sample outputs for different workload types"
                ]
            },
            {
                "number": 7,
                "title": "Sample Output Portfolio",
                "content": "Evidence That The Factory Produces Real Project Structures",
                "metrics": [
                    "Order management sample includes diagrams, code, infra, docs, tests, and deployment guide",
                    "Storage self-service sample includes API, worker, docs, and runnable tests",
                    "AKS sample demonstrates platform-focused infra and operational patterns",
                    "E-commerce sample shows lightweight web-facing outputs",
                    "Fabric Medallion sample demonstrates a data-pipeline architecture with governance, medallion stages, and Bicep assets",
                    "Developer portal reports readiness evidence across the sample portfolio",
                    "Validation suite runs directly from the portal"
                ]
            },
            {
                "number": 8,
                "title": "Use Cases",
                "content": "Ready for Any Workload",
                "metrics": [
                    "✓ E-commerce platforms (3 hrs to deployment)",
                    "✓ Data pipelines (2 hrs to deployment)",
                    "✓ Microservices architectures (2.5 hrs to deployment)",
                    "✓ Generative AI applications (1.5 hrs to deployment)",
                    "✓ Any custom architecture from requirements",
                    "✓ Enterprise compliance and governance patterns built-in"
                ]
            },
            {
                "number": 9,
                "title": "Financial Impact",
                "content": "Evidence-Based Readiness Impact",
                "metrics": [
                    "Repository evidence now reports measurable project completeness instead of projected business ROI",
                    f"Current portfolio baseline: {summary['project_count']} projects under readiness tracking",
                    f"Current production-like count: {summary['production_like_count']}",
                    f"Current runnable validation suites: {summary['testable_project_count']}",
                    "Leadership decision quality improves because readiness claims are tied to live artifacts and test output"
                ]
            },
            {
                "number": 10,
                "title": "Next Steps",
                "content": "Implementation Roadmap",
                "metrics": [
                    "✓ Platform production-ready (completed)",
                    "→ Raise remaining sample projects to full lifecycle completeness",
                    "→ Expand CI validation coverage to additional sample portfolios",
                    "→ Continue governance template hardening for production onboarding",
                    "→ Keep leadership messaging anchored to measured readiness evidence",
                    "→ Track readiness trendline over time in the developer portal"
                ]
            }
        ]
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Server error"}), 500

if __name__ == '__main__':
        parser = argparse.ArgumentParser(description='Run the Azure Architecture Factory demo portal.')
        parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '5000')))
        args = parser.parse_args()

        print("""
        ╔════════════════════════════════════════════════════════════════╗
        ║          Azure Architecture Factory - Demo Application         ║
        ║                  Starting on http://localhost:{port:<4}             ║
        ╚════════════════════════════════════════════════════════════════╝

        Visit:
            🎯 Main demo:       http://localhost:{port}/
            📊 Presentation:    http://localhost:{port}/presentation
            📋 Readiness:       http://localhost:{port}/factory-readiness
        """.format(port=args.port))
        debug_enabled = os.environ.get('FLASK_DEBUG') == '1'
        app.run(debug=debug_enabled, use_reloader=False, threaded=True, port=args.port)
