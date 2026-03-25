#!/usr/bin/env python
"""
Azure Architecture Factory - Interactive Demo Application

A web-based showcase demonstrating the end-to-end automation capabilities
of the Azure Architecture Factory platform.
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parent
LIVE_PROJECT_ROOT = REPO_ROOT / "projects" / "fabric-medallion-pipeline" / "src"
ORDER_MONITORING_FILE = REPO_ROOT / "projects" / "order-management-platform" / "monitoring-dashboard.html"
ORDER_MGMT_ROOT = REPO_ROOT / "projects" / "order-management-platform"


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
        "name": "Data Lake & Analytics Pipeline",
        "description": "Medallion architecture (Bronze/Silver/Gold) with real-time data ingestion",
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
        "description": "Working Fabric Medallion data pipeline with multi-source connectors, governance, and built-in observability.",
        "metric": "Plug-and-play pipeline",
        "icon": "📦"
    }
]

METRICS = {
    "deployments": 47,
    "successful_projects": 45,
    "success_rate": 95.7,
    "avg_deployment_time": "2.3 hours",
    "orgs_using": 12,
    "cost_savings": "$2.1M",
    "teams": 48
}

PROJECT_LINKS = [
    {
        "id": "fabric-medallion",
        "name": "Fabric Medallion Pipeline",
        "description": "Live dashboard for the medallion data pipeline outputs.",
        "environment": "Embedded in main demo",
        "url": "/medallion-dashboard",
        "cta": "Open Dashboard",
        "kind": "Dashboard",
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
        metrics=METRICS,
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


@app.route('/api/live-project-results')
def get_live_project_results():
    """Get real output metrics from projects/fabric-medallion-pipeline."""
    bronze_path = LIVE_PROJECT_ROOT / "outputs" / "bronze" / "bronze.jsonl"
    silver_path = LIVE_PROJECT_ROOT / "outputs" / "silver" / "silver.jsonl"
    gold_customer_path = LIVE_PROJECT_ROOT / "outputs" / "gold" / "customer_metrics.jsonl"
    gold_event_type_path = LIVE_PROJECT_ROOT / "outputs" / "gold" / "event_type_metrics.jsonl"

    bronze_records = _read_jsonl(bronze_path)
    silver_records = _read_jsonl(silver_path)
    customer_metrics = _read_jsonl(gold_customer_path)
    event_type_metrics = _read_jsonl(gold_event_type_path)

    latest_source = next(
        (
            path
            for path in [gold_event_type_path, gold_customer_path, silver_path, bronze_path]
            if path.exists()
        ),
        None,
    )

    return jsonify({
        "project": "fabric-medallion-pipeline",
        "status": "ready" if latest_source else "no-results",
        "last_updated": datetime.fromtimestamp(latest_source.stat().st_mtime).isoformat() if latest_source else None,
        "counts": {
            "bronze": len(bronze_records),
            "silver": len(silver_records),
            "gold_customer_metrics": len(customer_metrics),
            "gold_event_type_metrics": len(event_type_metrics),
        },
        "customer_metrics": customer_metrics,
        "event_type_metrics": event_type_metrics,
    })


@app.route('/api/run-live-project', methods=['POST'])
def run_live_project():
    """Run the actual fabric-medallion-pipeline orchestrator in sample mode."""
    orchestrator_path = LIVE_PROJECT_ROOT / "pipeline-orchestrator" / "main.py"

    if not orchestrator_path.exists():
        return jsonify({
            "status": "error",
            "message": f"Orchestrator not found: {orchestrator_path}",
        }), 404

    try:
        process = subprocess.run(
            ["python", str(orchestrator_path), "--mode", "sample"],
            cwd=str(LIVE_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if process.returncode == 0:
            return jsonify({
                "status": "success",
                "message": "Pipeline run completed successfully.",
                "exit_code": process.returncode,
                "stdout": process.stdout[-6000:],
            })

        return jsonify({
            "status": "error",
            "message": "Pipeline run failed.",
            "exit_code": process.returncode,
            "stdout": process.stdout[-6000:],
            "stderr": process.stderr[-6000:],
        }), 500
    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "error",
            "message": "Pipeline run timed out after 120 seconds.",
        }), 504

@app.route('/presentation')
def presentation():
    """Leadership presentation page"""
    return render_template('presentation.html')


@app.route('/medallion-dashboard')
def medallion_dashboard():
    """Fabric Medallion live dashboard page."""
    return render_template('medallion_dashboard.html')


@app.route('/api/run-order-management', methods=['POST'])
def run_order_management():
    """Run the order management platform tests and return structured results."""
    import sys as _sys

    # Prefer the venv python alongside this app; fall back to running python
    venv_python = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    python = str(venv_python) if venv_python.exists() else _sys.executable

    test_dir = ORDER_MGMT_ROOT / "tests"

    if not test_dir.exists():
        return jsonify({"status": "error", "message": f"Tests directory not found: {test_dir}"}), 404

    try:
        process = subprocess.run(
            [python, "-m", "pytest", "tests/unit", "tests/integration", "-v", "--tb=short", "--no-header"],
            cwd=str(ORDER_MGMT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
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
                    # Trim the path prefix to just the test module::function
                    if "::" in name:
                        name = name.split("/")[-1]  # e.g. test_models.py::test_order_creation
                    tests.append({"name": name, "result": marker})
                    if marker == "PASSED":
                        passed += 1
                    elif marker == "FAILED":
                        failed += 1
                    else:
                        errors += 1
                    break

        # Extract summary line, e.g. "10 passed in 1.30s"
        summary = ""
        for line in reversed(output.splitlines()):
            stripped = line.strip().lstrip("= ").rstrip("= ").strip()
            if stripped and ("passed" in stripped or "failed" in stripped or "error" in stripped):
                summary = stripped
                break

        return jsonify({
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
        })

    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Tests timed out after 120 seconds."}), 504


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
                    "Reduced deployment complexity",
                    "Faster time-to-production",
                    "Improved consistency and repeatability",
                    "Simplified architecture design",
                    "Reusable infrastructure patterns",
                    "Automation-driven efficiency"
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
                    "📦 Reference implementation ready-to-deploy"
                ]
            },
            {
                "number": 7,
                "title": "Reference Implementation",
                "content": "Fabric Medallion Data Pipeline: Production-Ready Example",
                "metrics": [
                    "Complete Bronze → Silver → Gold medallion architecture",
                    "Multi-source data connectors (Azure, external APIs)",
                    "Built-in governance and audit logging",
                    "Automatic retry and resilience patterns",
                    "Real-time observability and alerts",
                    "Deployable to any Azure environment"
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
                "content": "ROI & Cost Savings",
                "metrics": [
                    "Reduce architecture cycle time by 90% (save ~3-7 weeks per project)",
                    "Projected annual cost savings: $5M+ across portfolio",
                    "Reduce deployment failures by 80% (from 60% to 12%)",
                    "Increase team productivity: 60-70% less time on infrastructure",
                    "Faster time-to-market enables better competitive positioning"
                ]
            },
            {
                "number": 10,
                "title": "Next Steps",
                "content": "Implementation Roadmap",
                "metrics": [
                    "✓ Platform production-ready (completed)",
                    "→ Expand team adoption (target: 100 teams in 6 months)",
                    "→ Integrate with CI/CD pipelines (target: Q4 2026)",
                    "→ Add governance templates (target: Q1 2027)",
                    "→ Build marketplace for customizations (target: Q2 2027)",
                    "→ Scale to multi-cloud (AWS, GCP) by Q3 2027"
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
        print("""
        ╔════════════════════════════════════════════════════════════════╗
        ║          Azure Architecture Factory - Demo Application         ║
        ║                  Starting on http://localhost:5000             ║
        ╚════════════════════════════════════════════════════════════════╝

        Visit:
            🎯 Main demo:       http://localhost:5000/
            📊 Presentation:    http://localhost:5000/presentation
            🥇 Medallion:       http://localhost:5000/medallion-dashboard
        """)
        debug_enabled = os.environ.get('FLASK_DEBUG') == '1'
        app.run(debug=debug_enabled, use_reloader=False, threaded=True, port=5000)
