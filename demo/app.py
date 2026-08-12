#!/usr/bin/env python
"""
Azure Architecture Factory - Interactive Demo Application

A web-based showcase demonstrating the end-to-end automation capabilities
of the Azure Architecture Factory platform.
"""

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path
from uuid import uuid4

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parent
ORDER_MONITORING_FILE = REPO_ROOT / "projects" / "order-management-platform" / "monitoring-dashboard.html"
ORDER_MGMT_ROOT = REPO_ROOT / "projects" / "order-management-platform"
STORAGE_SELF_SERVICE_ROOT = REPO_ROOT / "projects" / "storage-self-service-provisioning"
FABRIC_MEDALLION_ROOT = REPO_ROOT / "projects" / "fabric-medallion-pipeline"
APP_PACKS_DIR = REPO_ROOT / "factory-templates" / "application-zone" / "packs"
AAPAAS_ROOT = Path(
    os.environ.get(
        "AAPAAS_ROOT",
        str(REPO_ROOT / "factory-templates" / "application-zone" / "aapaas"),
    )
)
AAPAAS_APP_PACKS_DIR = AAPAAS_ROOT / "app-packs"
AAPAAS_AGENT_PACKS_DIR = AAPAAS_ROOT / "agent-packs"
AAPAAS_CERTIFICATION_FILE = AAPAAS_ROOT / "certification" / "reports" / "certification-summary.generated.json"
AAPAAS_INSTANCES_DIR = AAPAAS_ROOT / "operations" / "instances"
AAPAAS_HEALTH_DIR = AAPAAS_ROOT / "operations" / "health"
AAPAAS_SCHEDULER_REPORT = AAPAAS_ROOT / "operations" / "scheduler" / "casewright-scheduler.generated.json"

APP_ZONE_INSTANCES: dict[str, dict] = {}
APP_ZONE_RUNS: dict[str, list[dict]] = {}

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


def _app_pack_key(pack_id: str, version: str) -> str:
    return f"{pack_id}:{version}"


def _agent_pack_key(agent_pack_id: str, version: str) -> str:
    return f"{agent_pack_id}:{version}"


def _factory_template_url(path: Path) -> str | None:
    templates_root = (REPO_ROOT / "factory-templates").resolve()
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(templates_root)
    except (OSError, ValueError):
        return None
    if not resolved.is_file():
        return None
    return f"/factory-templates/{relative.as_posix()}"


def _add_documentation_link(links: list[dict], label: str, path: Path) -> None:
    href = _factory_template_url(path)
    if not href or any(item.get("href") == href for item in links):
        return
    links.append({"label": label, "href": href})


def _documentation_path_candidates(value: str, manifest_path: Path) -> list[Path]:
    normalized = value.strip().replace("\\", "/").lstrip("/")
    if not normalized or "://" in normalized:
        return []
    if normalized.startswith("factory-templates/"):
        return [REPO_ROOT / normalized]
    return [
        manifest_path.parent / normalized,
        REPO_ROOT / normalized,
    ]


def _collect_manifest_documentation_links(manifest: dict, manifest_path: Path) -> list[dict]:
    links: list[dict] = []

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "documentation":
                    docs = child if isinstance(child, list) else [child]
                    for doc in docs:
                        if not isinstance(doc, str):
                            continue
                        for candidate in _documentation_path_candidates(doc, manifest_path):
                            if candidate.is_file():
                                _add_documentation_link(links, "Docs", candidate)
                                break
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(manifest)
    return links


def _app_pack_documentation_links(pack: dict, certification: dict) -> list[dict]:
    links: list[dict] = []
    manifest_path = Path(pack.get("_portal", {}).get("manifestPath", ""))
    if manifest_path:
        _add_documentation_link(links, "Manifest", manifest_path)
        links.extend(_collect_manifest_documentation_links(pack, manifest_path))

    pack_id = pack.get("metadata", {}).get("packId")
    report_name = certification.get("ReportPath") or (f"{pack_id}-certification.md" if pack_id else "")
    if report_name:
        _add_documentation_link(
            links,
            "Certification",
            AAPAAS_ROOT / "certification" / "reports" / str(report_name),
        )
    return links


def _agent_pack_documentation_links(agent_pack: dict) -> list[dict]:
    links: list[dict] = []
    manifest_path = Path(agent_pack.get("_portal", {}).get("manifestPath", ""))
    if manifest_path:
        _add_documentation_link(links, "AgentPack manifest", manifest_path)

    metadata = agent_pack.get("metadata", {})
    agent_pack_id = metadata.get("agentPackId")
    if agent_pack_id:
        _add_documentation_link(
            links,
            "Certification",
            AAPAAS_ROOT / "certification" / "reports" / f"{agent_pack_id}-certification.md",
        )

    parent_pack_id = metadata.get("parentAppPackId")
    parent_version = metadata.get("parentAppPackVersion") or metadata.get("version")
    if parent_pack_id:
        parent_manifest = AAPAAS_APP_PACKS_DIR / str(parent_pack_id) / str(parent_version) / "manifest.json"
        if not parent_manifest.is_file():
            parent_manifest = AAPAAS_APP_PACKS_DIR / str(parent_pack_id) / "1.0.0" / "manifest.json"
        _add_documentation_link(links, "Parent manifest", parent_manifest)
        _add_documentation_link(
            links,
            "Parent certification",
            AAPAAS_ROOT / "certification" / "reports" / f"{parent_pack_id}-certification.md",
        )

    _add_documentation_link(links, "AgentPack schema", AAPAAS_ROOT / "docs" / "AGENTPACK_SCHEMA.md")
    return links


def _load_app_packs() -> dict[str, dict]:
    registry: dict[str, dict] = {}

    # Load built-in AAF packs first, then let the AAPAAS workspace overlay/enrich them.
    for root, source in ((APP_PACKS_DIR, "aaf"), (AAPAAS_APP_PACKS_DIR, "aapaas")):
        if not root.exists():
            continue
        for path in sorted(root.glob("**/manifest.json")):
            doc = _read_json(path)
            if not doc:
                continue

            metadata = doc.get("metadata", {})
            pack_id = metadata.get("packId")
            version = metadata.get("version")
            if not pack_id or not version:
                continue

            doc = dict(doc)
            doc["_portal"] = {
                "source": source,
                "manifestPath": str(path),
            }
            registry[_app_pack_key(pack_id, version)] = doc

    return registry


def _load_agent_packs() -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for root, source in ((AAPAAS_AGENT_PACKS_DIR, "aapaas"),):
        if not root.exists():
            continue
        for path in sorted(root.glob("**/manifest.json")):
            doc = _read_json(path)
            if not isinstance(doc, dict) or doc.get("kind") != "AgentPack":
                continue
            metadata = doc.get("metadata", {})
            agent_pack_id = metadata.get("agentPackId")
            version = metadata.get("version")
            if not agent_pack_id or not version:
                continue
            doc = dict(doc)
            doc["_portal"] = {
                "source": source,
                "manifestPath": str(path),
            }
            registry[_agent_pack_key(str(agent_pack_id), str(version))] = doc
    return registry


def _load_aapaas_certifications() -> dict[str, dict]:
    """Return certification records keyed by packId:version."""
    records = _read_json(AAPAAS_CERTIFICATION_FILE)
    if not isinstance(records, list):
        return {}

    result: dict[str, dict] = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        pack_id = item.get("PackId")
        version = item.get("Version")
        if pack_id and version:
            result[_app_pack_key(str(pack_id), str(version))] = item
    return result


def _load_aapaas_instances() -> list[dict]:
    instances: list[dict] = []
    if not AAPAAS_INSTANCES_DIR.exists():
        return instances

    for path in sorted(AAPAAS_INSTANCES_DIR.glob("*.instance.json")):
        doc = _read_json(path)
        if not isinstance(doc, dict):
            continue
        metadata = doc.get("metadata", {})
        runtime = doc.get("runtime", {})
        azure = doc.get("azure", {})
        instances.append({
            "instanceId": metadata.get("instanceId"),
            "packId": metadata.get("packId"),
            "packVersion": metadata.get("packVersion"),
            "displayName": metadata.get("displayName"),
            "status": metadata.get("status"),
            "resourceGroup": azure.get("resourceGroup"),
            "location": azure.get("location"),
            "apiBaseUrl": runtime.get("apiBaseUrl"),
            "healthStatus": runtime.get("healthStatus"),
            "manifestPath": str(path),
        })
    return instances


def _load_aapaas_health() -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not AAPAAS_HEALTH_DIR.exists():
        return result
    for path in sorted(AAPAAS_HEALTH_DIR.glob("*.health.generated.json")):
        doc = _read_json(path)
        if not doc:
            continue
        checks = doc if isinstance(doc, list) else [doc]
        instance_id = None
        if checks and isinstance(checks[0], dict):
            instance_id = checks[0].get("instanceId")
        if instance_id:
            result[str(instance_id)] = {
                "checks": checks,
                "path": str(path),
            }
    return result


def _load_aapaas_scheduler_report() -> dict:
    doc = _read_json(AAPAAS_SCHEDULER_REPORT)
    return doc if isinstance(doc, dict) else {}


def _get_pack_or_none(pack_id: str, version: str) -> dict | None:
    registry = _load_app_packs()
    return registry.get(_app_pack_key(pack_id, version))


def _list_pack_versions(pack_id: str) -> list[dict]:
    registry = _load_app_packs()
    versions = [
        value
        for value in registry.values()
        if value.get("metadata", {}).get("packId") == pack_id
    ]
    versions.sort(key=lambda item: item.get("metadata", {}).get("version", ""), reverse=True)
    return versions


def _build_pack_catalog() -> list[dict]:
    registry = _load_app_packs()
    certs = _load_aapaas_certifications()
    instances = _load_aapaas_instances()
    grouped: dict[str, list[dict]] = {}
    for pack in registry.values():
        pack_id = pack.get("metadata", {}).get("packId")
        if not pack_id:
            continue
        grouped.setdefault(pack_id, []).append(pack)

    catalog = []
    for pack_id, versions in grouped.items():
        versions.sort(key=lambda item: item.get("metadata", {}).get("version", ""), reverse=True)
        latest = versions[0]
        required_inputs = latest.get("inputs", {}).get("required", [])
        key = _app_pack_key(pack_id, latest.get("metadata", {}).get("version", ""))
        certification = certs.get(key, {})
        pack_instances = [
            item
            for item in instances
            if item.get("packId") == pack_id
            and item.get("packVersion") == latest.get("metadata", {}).get("version")
        ]

        catalog.append({
            "packId": pack_id,
            "displayName": latest.get("metadata", {}).get("displayName", pack_id),
            "latestVersion": latest.get("metadata", {}).get("version"),
            "status": latest.get("metadata", {}).get("status", "unknown"),
            "owner": latest.get("metadata", {}).get("owner", "unknown"),
            "supportTier": latest.get("metadata", {}).get("supportTier", "unknown"),
            "source": latest.get("_portal", {}).get("source", "aaf"),
            "certificationStatus": certification.get("Status"),
            "certificationWarnings": certification.get("Warnings", 0),
            "certificationBlockers": certification.get("Blockers", 0),
            "instanceCount": len(pack_instances),
            "instances": pack_instances,
            "supportedRegions": latest.get("compatibility", {}).get("supportedRegions", []),
            "requiredInputCount": len(required_inputs),
            "requiredServices": latest.get("compatibility", {}).get("requiredServices", []),
            "documentationLinks": _app_pack_documentation_links(latest, certification),
            "versions": [v.get("metadata", {}).get("version") for v in versions],
        })

    catalog.sort(key=lambda item: item["displayName"].lower())
    return catalog


def _build_agent_pack_catalog() -> list[dict]:
    registry = _load_agent_packs()
    grouped: dict[str, list[dict]] = {}
    for pack in registry.values():
        agent_pack_id = pack.get("metadata", {}).get("agentPackId")
        if not agent_pack_id:
            continue
        grouped.setdefault(agent_pack_id, []).append(pack)

    catalog = []
    for agent_pack_id, versions in grouped.items():
        versions.sort(key=lambda item: item.get("metadata", {}).get("version", ""), reverse=True)
        latest = versions[0]
        metadata = latest.get("metadata", {})
        runtime = latest.get("runtime", {})
        contract = latest.get("contract", {})
        governance = latest.get("governance", {})
        catalog.append({
            "offeringType": "agent-pack",
            "agentPackId": agent_pack_id,
            "displayName": metadata.get("displayName", agent_pack_id),
            "latestVersion": metadata.get("version"),
            "status": metadata.get("status", "unknown"),
            "owner": metadata.get("owner", "unknown"),
            "supportTier": metadata.get("supportTier", "unknown"),
            "source": latest.get("_portal", {}).get("source", "aapaas"),
            "parentAppPackId": metadata.get("parentAppPackId"),
            "canonicalSource": metadata.get("canonicalSource", "casewright"),
            "executionMode": runtime.get("executionMode", "unknown"),
            "runtimeEndpoint": runtime.get("defaultRuntimeEndpoint"),
            "toolCount": len(contract.get("tools", [])),
            "capabilities": contract.get("capabilities", []),
            "dataBoundary": governance.get("dataBoundary", ""),
            "certificationStatus": governance.get("certificationStatus"),
            "requiredEvidence": governance.get("requiredEvidence", []),
            "documentationLinks": _agent_pack_documentation_links(latest),
            "versions": [v.get("metadata", {}).get("version") for v in versions],
        })

    catalog.sort(key=lambda item: item["displayName"].lower())
    return catalog


def _validate_input_rule(rule: dict, value) -> str | None:
    field_type = rule.get("type")
    name = rule.get("name", "field")
    allowed_values = rule.get("allowedValues", [])

    if field_type == "string":
        if not isinstance(value, str) or not value.strip():
            return f"{name} must be a non-empty string"
    elif field_type == "enum":
        if value not in allowed_values:
            return f"{name} must be one of: {', '.join(allowed_values)}"
    elif field_type == "integer":
        if not isinstance(value, int):
            return f"{name} must be an integer"
    elif field_type == "boolean":
        if not isinstance(value, bool):
            return f"{name} must be a boolean"
    elif field_type == "object":
        if not isinstance(value, dict):
            return f"{name} must be an object"
        required_fields = rule.get("requiredFields", [])
        for field in required_fields:
            if field not in value:
                return f"{name}.{field} is required"

    return None


def _validate_pack_inputs(pack: dict, inputs: dict) -> list[str]:
    errors: list[str] = []
    required_rules = pack.get("inputs", {}).get("required", [])
    optional_rules = pack.get("inputs", {}).get("optional", [])

    for rule in required_rules:
        name = rule.get("name")
        if name not in inputs:
            errors.append(f"Missing required input: {name}")
            continue

        rule_error = _validate_input_rule(rule, inputs.get(name))
        if rule_error:
            errors.append(rule_error)

    optional_by_name = {rule.get("name"): rule for rule in optional_rules}
    required_by_name = {rule.get("name"): rule for rule in required_rules}

    for name, value in inputs.items():
        if name in required_by_name:
            continue
        if name in optional_by_name:
            rule_error = _validate_input_rule(optional_by_name[name], value)
            if rule_error:
                errors.append(rule_error)

    return errors


def _append_instance_run(instance_id: str, run_type: str, status: str, details: dict | None = None) -> None:
    APP_ZONE_RUNS.setdefault(instance_id, [])
    APP_ZONE_RUNS[instance_id].append({
        "runId": str(uuid4()),
        "type": run_type,
        "status": status,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
    })


def _normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def _sanitize_instance(instance: dict) -> dict:
    sanitized = dict(instance)
    runtime = dict(sanitized.get("runtime", {}))
    if "apiKey" in runtime:
        runtime["apiKey"] = "***"
    if "headers" in runtime:
        headers = dict(runtime.get("headers") or {})
        if "Authorization" in headers:
            headers["Authorization"] = "***"
        if "x-api-key" in headers:
            headers["x-api-key"] = "***"
        runtime["headers"] = headers
    sanitized["runtime"] = runtime
    return sanitized


def _proxy_runtime_request(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    api_key: str | None = None,
    headers: dict | None = None,
    timeout: int = 30,
) -> tuple[int, dict]:
    normalized_base = _normalize_base_url(base_url)
    request_path = path if path.startswith("/") else f"/{path}"
    url = f"{normalized_base}{request_path}"

    request_headers = {
        "Accept": "application/json",
    }
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if api_key:
        request_headers["x-api-key"] = api_key
    if headers:
        request_headers.update(headers)

    body_bytes = None
    if payload is not None:
        body_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=body_bytes, method=method.upper(), headers=request_headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8") if response.length != 0 else ""
            if raw:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = {"raw": raw}
            else:
                parsed = {}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else {"error": str(exc)}
        except json.JSONDecodeError:
            parsed = {"error": str(exc), "raw": raw}
        return exc.code, parsed
    except urllib.error.URLError as exc:
        return 502, {"error": f"Runtime unreachable: {exc.reason}"}


def _default_agent_services_for_pack(pack_id: str) -> list[dict]:
    if pack_id == "casewright":
        return [
            {
                "agentId": "casewright-health-agent",
                "displayName": "CaseWright Health Agent",
                "description": "Checks runtime readiness and service health.",
                "method": "GET",
                "path": "/health",
                "category": "operations",
            },
            {
                "agentId": "casewright-chat-agent",
                "displayName": "CaseWright Knowledge Chat Agent",
                "description": "Answers case and policy questions with grounded retrieval.",
                "method": "POST",
                "path": "/api/chat/query",
                "category": "knowledge",
                "samplePayload": {
                    "query": "Summarize the key contract dispute factors in this case.",
                    "user_id": "portal-user",
                    "session_id": "portal-session",
                },
            },
            {
                "agentId": "casewright-sharepoint-sync-agent",
                "displayName": "CaseWright SharePoint Sync Agent",
                "description": "Triggers SharePoint site synchronization workflows.",
                "method": "POST",
                "path": "/api/sharepoint/sites/sync",
                "category": "ingestion",
                "samplePayload": {
                    "site_id": "<sharepoint-site-id>",
                    "force": False,
                },
            },
            {
                "agentId": "casewright-indexer-agent",
                "displayName": "CaseWright Indexer Agent",
                "description": "Runs or checks retrieval index pipeline operations.",
                "method": "GET",
                "path": "/api/pipeline/indexer-status",
                "category": "pipeline",
            },
        ]

    return [
        {
            "agentId": "generic-health-agent",
            "displayName": "Generic Health Agent",
            "description": "Checks app runtime health endpoint.",
            "method": "GET",
            "path": "/health",
            "category": "operations",
        }
    ]


def _agent_services_for_pack(pack: dict) -> list[dict]:
    declared = pack.get("agentServices")
    if isinstance(declared, list) and declared:
        return declared
    pack_id = pack.get("metadata", {}).get("packId", "")
    return _default_agent_services_for_pack(pack_id)


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
    """Serve the deployed-style factory portal as the primary local experience."""
    portal_path = REPO_ROOT / "factory-portal.html"
    if portal_path.exists():
        return send_file(portal_path)

    # Fallback to the legacy template only if the new portal file is missing.
    return render_template(
        'index.html',
        scenarios=DEMO_SCENARIOS,
        benefits=BENEFITS,
        metrics=_build_demo_metrics(),
        project_links=PROJECT_LINKS,
    )


@app.route('/legacy-demo')
def legacy_demo():
    """Legacy demo page retained for compatibility and side-by-side comparison."""
    return render_template(
        'index.html',
        scenarios=DEMO_SCENARIOS,
        benefits=BENEFITS,
        metrics=_build_demo_metrics(),
        project_links=PROJECT_LINKS,
    )


@app.route('/assets/<path:asset_path>')
def serve_repo_assets(asset_path):
    """Serve root-level portal assets when running via the demo Flask app."""
    return send_from_directory(REPO_ROOT / "assets", asset_path)


@app.route('/docs/<path:doc_path>')
def serve_repo_docs(doc_path):
    """Serve root-level docs used by the deployed-style portal previews."""
    return send_from_directory(REPO_ROOT / "docs", doc_path)


@app.route('/factory-templates/<path:template_path>')
def serve_factory_template(template_path):
    """Serve factory template evidence linked from the local catalog preview."""
    return send_from_directory(REPO_ROOT / "factory-templates", template_path)


@app.route('/factory-projects.generated.json')
def serve_generated_projects_file():
    """Serve generated project listing expected by the deployed-style portal."""
    file_path = REPO_ROOT / "factory-projects.generated.json"
    if not file_path.exists():
        return jsonify({"error": "factory-projects.generated.json not found"}), 404
    return send_file(file_path)

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


@app.route('/api/me')
def get_current_user():
    """Return a local user profile compatible with the deployed portal UI."""
    return jsonify({
        "name": "Local Demo User",
        "email": "local.demo@aaf",
        "auth_mode": "local",
        "is_admin": True,
    })


@app.route('/api/csa-copilot/tools')
def get_csa_copilot_tools():
    """Return CSA companion tool metadata for local preview mode."""
    return jsonify({
        "tools": [
            {"name": "best_practices", "description": "Guidance for Azure security and reliability."},
            {"name": "troubleshooting", "description": "Production diagnostics and triage patterns."},
        ]
    })


@app.route('/api/csa-copilot/ask', methods=['POST'])
def ask_csa_copilot():
    """Provide a deterministic local response for CSA companion queries."""
    payload = request.json or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    return jsonify({
        "answer": (
            "Local CSA companion preview is active. "
            "For production guidance, validate identity, network boundaries, and observability baselines first."
        ),
        "question": question,
        "source": "local-demo",
    })


@app.route('/api/application-zone/packs')
def get_application_zone_packs():
    """Return the offering catalog for the Application Zone."""
    packs = _build_pack_catalog()
    agent_packs = _build_agent_pack_catalog()
    return jsonify({
        "updated_at": datetime.now().isoformat(),
        "packs": packs,
        "agentPacks": agent_packs,
        "offerings": (
            [dict(item, offeringType="app-pack") for item in packs]
            + agent_packs
        ),
    })


@app.route('/api/application-zone/aapaas/summary')
def get_aapaas_summary():
    """Return AAPAAS service evidence for the Application Zone dashboard."""
    instances = _load_aapaas_instances()
    health = _load_aapaas_health()
    scheduler = _load_aapaas_scheduler_report()
    certifications = list(_load_aapaas_certifications().values())
    agent_packs = _build_agent_pack_catalog()

    healthy_instances = [
        instance for instance in instances
        if str(instance.get("healthStatus", "")).lower() in {"passed", "healthy"}
    ]

    return jsonify({
        "updated_at": datetime.now().isoformat(),
        "workspace": str(AAPAAS_ROOT),
        "instances": instances,
        "health": health,
        "scheduler": scheduler,
        "certifications": certifications,
        "agentPacks": agent_packs,
        "summary": {
            "instanceCount": len(instances),
            "healthyInstanceCount": len(healthy_instances),
            "certificationReadyCount": len([
                item for item in certifications
                if item.get("Status") == "certification-ready"
            ]),
            "candidateWithGapsCount": len([
                item for item in certifications
                if item.get("Status") == "candidate-with-gaps"
            ]),
            "agentPackCount": len(agent_packs),
            "hostedAgentPackCount": len([
                item for item in agent_packs
                if item.get("executionMode") == "hosted"
            ]),
            "schedulerStatus": scheduler.get("syncResult", {}).get("status"),
        },
    })


@app.route('/api/application-zone/packs/<pack_id>/versions')
def get_application_zone_pack_versions(pack_id):
    """Return available versions for a given app pack ID."""
    versions = _list_pack_versions(pack_id)
    if not versions:
        return jsonify({"error": f"App pack not found: {pack_id}"}), 404

    return jsonify({
        "packId": pack_id,
        "versions": [pack.get("metadata", {}).get("version") for pack in versions],
    })


@app.route('/api/application-zone/packs/<pack_id>/versions/<version>')
def get_application_zone_pack_version(pack_id, version):
    """Return the full app pack manifest for a specific version."""
    pack = _get_pack_or_none(pack_id, version)
    if not pack:
        return jsonify({"error": f"App pack version not found: {pack_id}@{version}"}), 404
    return jsonify(pack)


@app.route('/api/application-zone/validate-inputs', methods=['POST'])
def validate_application_zone_inputs():
    """Validate user-provided deployment inputs against app pack rules."""
    payload = request.json or {}
    pack_id = payload.get("packId")
    version = payload.get("version")
    inputs = payload.get("inputs", {})

    if not pack_id or not version:
        return jsonify({"error": "packId and version are required"}), 400
    if not isinstance(inputs, dict):
        return jsonify({"error": "inputs must be an object"}), 400

    pack = _get_pack_or_none(pack_id, version)
    if not pack:
        return jsonify({"error": f"App pack version not found: {pack_id}@{version}"}), 404

    errors = _validate_pack_inputs(pack, inputs)
    return jsonify({
        "packId": pack_id,
        "version": version,
        "valid": len(errors) == 0,
        "errors": errors,
    })


@app.route('/api/application-zone/instances', methods=['POST'])
def create_application_zone_instance():
    """Create an Application Zone instance after input validation."""
    payload = request.json or {}
    pack_id = payload.get("packId")
    version = payload.get("version")
    profile = payload.get("profile", "dev")
    inputs = payload.get("inputs", {})

    if not pack_id or not version:
        return jsonify({"error": "packId and version are required"}), 400
    if not isinstance(inputs, dict):
        return jsonify({"error": "inputs must be an object"}), 400

    pack = _get_pack_or_none(pack_id, version)
    if not pack:
        return jsonify({"error": f"App pack version not found: {pack_id}@{version}"}), 404

    errors = _validate_pack_inputs(pack, inputs)
    if errors:
        return jsonify({
            "error": "Validation failed",
            "valid": False,
            "errors": errors,
        }), 400

    instance_id = f"az-inst-{uuid4().hex[:10]}"
    now = datetime.now().isoformat()

    APP_ZONE_INSTANCES[instance_id] = {
        "instanceId": instance_id,
        "packId": pack_id,
        "version": version,
        "displayName": pack.get("metadata", {}).get("displayName", pack_id),
        "profile": profile,
        "state": "Provisioned",
        "createdAt": now,
        "updatedAt": now,
        "inputs": inputs,
        "runtime": {
            "mode": "simulation",
            "baseUrl": "",
            "connected": False,
            "capabilities": [],
            "lastHealth": None,
        },
        "agentServices": _agent_services_for_pack(pack),
    }

    runtime_input = inputs.get("runtime") if isinstance(inputs, dict) else None
    if isinstance(runtime_input, dict) and runtime_input.get("baseUrl"):
        base_url = _normalize_base_url(str(runtime_input.get("baseUrl", "")))
        api_key = str(runtime_input.get("apiKey", "")).strip() or None
        connect_headers = runtime_input.get("headers") if isinstance(runtime_input.get("headers"), dict) else None

        status_code, health_payload = _proxy_runtime_request(
            base_url=base_url,
            path="/api/health",
            method="GET",
            api_key=api_key,
            headers=connect_headers,
            timeout=15,
        )

        if status_code >= 400:
            status_code, health_payload = _proxy_runtime_request(
                base_url=base_url,
                path="/health",
                method="GET",
                api_key=api_key,
                headers=connect_headers,
                timeout=15,
            )

        connected = status_code < 400
        APP_ZONE_INSTANCES[instance_id]["runtime"] = {
            "mode": "proxy",
            "baseUrl": base_url,
            "apiKey": api_key,
            "headers": connect_headers or {},
            "connected": connected,
            "capabilities": [
                "/api/health",
                "/api/chat",
                "/api/chat/query",
                "/api/sharepoint/sites",
                "/api/sharepoint/sites/sync",
                "/api/pipeline/indexer-status",
                "/api/pipeline/run-indexer",
            ],
            "lastHealth": {
                "status": status_code,
                "payload": health_payload,
                "checkedAt": datetime.now().isoformat(),
            },
        }
        APP_ZONE_INSTANCES[instance_id]["agentServices"] = _agent_services_for_pack(pack)
        APP_ZONE_INSTANCES[instance_id]["state"] = "Connected" if connected else "Provisioned"
        APP_ZONE_INSTANCES[instance_id]["updatedAt"] = datetime.now().isoformat()

        _append_instance_run(
            instance_id,
            run_type="connect-runtime",
            status="success" if connected else "warning",
            details={
                "baseUrl": base_url,
                "healthStatus": status_code,
                "healthPayload": health_payload,
            },
        )

    _append_instance_run(
        instance_id,
        run_type="provision",
        status="success",
        details={
            "message": "Instance created in simulation mode",
            "profile": profile,
        },
    )

    return jsonify({
        "status": "created",
        "instance": _sanitize_instance(APP_ZONE_INSTANCES[instance_id]),
    }), 201


@app.route('/api/application-zone/instances/<instance_id>')
def get_application_zone_instance(instance_id):
    """Return a single Application Zone instance."""
    instance = APP_ZONE_INSTANCES.get(instance_id)
    if not instance:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404
    return jsonify(_sanitize_instance(instance))


@app.route('/api/application-zone/instances/<instance_id>/runs')
def get_application_zone_instance_runs(instance_id):
    """Return run history for a single Application Zone instance."""
    if instance_id not in APP_ZONE_INSTANCES:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404

    runs = APP_ZONE_RUNS.get(instance_id, [])
    return jsonify({
        "instanceId": instance_id,
        "runs": runs,
    })


@app.route('/api/application-zone/instances/<instance_id>/connect-runtime', methods=['POST'])
def connect_application_zone_runtime(instance_id):
    """Connect an existing app-zone instance to a real runtime endpoint (proxy mode)."""
    instance = APP_ZONE_INSTANCES.get(instance_id)
    if not instance:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404

    payload = request.json or {}
    base_url = _normalize_base_url(str(payload.get("baseUrl", "")))
    api_key = str(payload.get("apiKey", "")).strip() or None
    extra_headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else None

    if not base_url:
        return jsonify({"error": "baseUrl is required"}), 400

    status_code, health_payload = _proxy_runtime_request(
        base_url=base_url,
        path="/api/health",
        method="GET",
        api_key=api_key,
        headers=extra_headers,
        timeout=15,
    )
    if status_code >= 400:
        status_code, health_payload = _proxy_runtime_request(
            base_url=base_url,
            path="/health",
            method="GET",
            api_key=api_key,
            headers=extra_headers,
            timeout=15,
        )

    connected = status_code < 400
    instance["runtime"] = {
        "mode": "proxy",
        "baseUrl": base_url,
        "apiKey": api_key,
        "headers": extra_headers or {},
        "connected": connected,
        "capabilities": [
            "/api/health",
            "/api/chat",
            "/api/chat/query",
            "/api/sharepoint/sites",
            "/api/sharepoint/sites/sync",
            "/api/pipeline/indexer-status",
            "/api/pipeline/run-indexer",
        ],
        "lastHealth": {
            "status": status_code,
            "payload": health_payload,
            "checkedAt": datetime.now().isoformat(),
        },
    }
    instance["state"] = "Connected" if connected else "Provisioned"
    instance["updatedAt"] = datetime.now().isoformat()

    _append_instance_run(
        instance_id,
        run_type="connect-runtime",
        status="success" if connected else "warning",
        details={
            "baseUrl": base_url,
            "healthStatus": status_code,
            "healthPayload": health_payload,
        },
    )

    return jsonify({
        "status": "connected" if connected else "warning",
        "instance": _sanitize_instance(instance),
        "health": {
            "status": status_code,
            "payload": health_payload,
        },
    }), (200 if connected else 207)


@app.route('/api/application-zone/instances/<instance_id>/capabilities')
def get_application_zone_instance_capabilities(instance_id):
    """Return runtime capability metadata for a connected app-zone instance."""
    instance = APP_ZONE_INSTANCES.get(instance_id)
    if not instance:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404

    runtime = instance.get("runtime", {})
    return jsonify({
        "instanceId": instance_id,
        "runtimeMode": runtime.get("mode", "simulation"),
        "connected": runtime.get("connected", False),
        "baseUrl": runtime.get("baseUrl", ""),
        "capabilities": runtime.get("capabilities", []),
        "lastHealth": runtime.get("lastHealth"),
    })


@app.route('/api/application-zone/instances/<instance_id>/invoke', methods=['POST'])
def invoke_application_zone_runtime(instance_id):
    """Proxy arbitrary requests to a connected runtime for app-zone platform access."""
    instance = APP_ZONE_INSTANCES.get(instance_id)
    if not instance:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404

    runtime = instance.get("runtime", {})
    base_url = runtime.get("baseUrl")
    if runtime.get("mode") != "proxy" or not base_url:
        return jsonify({"error": "Instance is not connected to a runtime"}), 400

    payload = request.json or {}
    path = str(payload.get("path", "")).strip()
    method = str(payload.get("method", "GET")).strip().upper()
    body = payload.get("body")
    headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else None

    if not path:
        return jsonify({"error": "path is required"}), 400

    status_code, proxied = _proxy_runtime_request(
        base_url=base_url,
        path=path,
        method=method,
        payload=body if isinstance(body, dict) else None,
        api_key=runtime.get("apiKey"),
        headers={**(runtime.get("headers") or {}), **(headers or {})},
    )

    _append_instance_run(
        instance_id,
        run_type="invoke-runtime",
        status="success" if status_code < 400 else "failed",
        details={
            "method": method,
            "path": path,
            "status": status_code,
        },
    )

    return jsonify({
        "instanceId": instance_id,
        "status": status_code,
        "method": method,
        "path": path,
        "response": proxied,
    }), (200 if status_code < 400 else 502)


@app.route('/api/application-zone/instances/<instance_id>/agents')
def list_application_zone_agents(instance_id):
    """List available agents for an app instance."""
    instance = APP_ZONE_INSTANCES.get(instance_id)
    if not instance:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404

    pack_id = instance.get("packId")
    version = instance.get("version")
    pack = _get_pack_or_none(pack_id, version)
    if not pack:
        return jsonify({"agents": [], "services": []})

    agents = pack.get("agents", [])
    services = pack.get("services", [])
    return jsonify({
        "instanceId": instance_id,
        "packId": pack_id,
        "agents": agents,
        "services": services,
    })


@app.route('/api/application-zone/instances/<instance_id>/agents/<agent_id>/invoke', methods=['POST'])
def invoke_application_zone_agent(instance_id, agent_id):
    """Invoke a specific agent within an app instance."""
    instance = APP_ZONE_INSTANCES.get(instance_id)
    if not instance:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404

    runtime = instance.get("runtime", {})
    base_url = runtime.get("baseUrl")
    if runtime.get("mode") != "proxy" or not base_url:
        return jsonify({"error": "Instance is not connected to a runtime"}), 400

    pack_id = instance.get("packId")
    version = instance.get("version")
    pack = _get_pack_or_none(pack_id, version)
    if not pack:
        return jsonify({"error": "App pack not found"}), 404

    agents = pack.get("agents", [])
    agent = next((a for a in agents if a.get("agentId") == agent_id), None)
    if not agent:
        return jsonify({"error": f"Agent not found: {agent_id}"}), 404

    payload = request.json or {}
    endpoint = payload.get("endpoint")
    method = str(payload.get("method", "POST")).upper()
    body = payload.get("body")

    if not endpoint:
        endpoint = agent.get("endpoints", {}).get("query", "/api/chat/query")

    status_code, proxied = _proxy_runtime_request(
        base_url=base_url,
        path=endpoint,
        method=method,
        payload=body if isinstance(body, dict) else None,
        api_key=runtime.get("apiKey"),
        headers=runtime.get("headers") or {},
    )

    _append_instance_run(
        instance_id,
        run_type=f"agent-invoke-{agent_id}",
        status="success" if status_code < 400 else "failed",
        details={"agentId": agent_id, "endpoint": endpoint, "status": status_code},
    )

    return jsonify({
        "instanceId": instance_id,
        "agentId": agent_id,
        "status": status_code,
        "response": proxied,
    }), (200 if status_code < 400 else 502)


@app.route('/api/application-zone/instances/<instance_id>/casewright/chat-query', methods=['POST'])
def invoke_casewright_chat_query(instance_id):
    """Convenience endpoint to call the CaseWright /api/chat/query route through runtime proxy."""
    instance = APP_ZONE_INSTANCES.get(instance_id)
    if not instance:
        return jsonify({"error": f"Instance not found: {instance_id}"}), 404

    runtime = instance.get("runtime", {})
    base_url = runtime.get("baseUrl")
    if runtime.get("mode") != "proxy" or not base_url:
        return jsonify({"error": "Instance is not connected to a runtime"}), 400

    payload = request.json or {}
    status_code, proxied = _proxy_runtime_request(
        base_url=base_url,
        path="/api/chat/query",
        method="POST",
        payload=payload,
        api_key=runtime.get("apiKey"),
        headers=runtime.get("headers") or {},
    )

    _append_instance_run(
        instance_id,
        run_type="casewright-chat-query",
        status="success" if status_code < 400 else "failed",
        details={"status": status_code},
    )

    return jsonify({
        "instanceId": instance_id,
        "status": status_code,
        "response": proxied,
    }), (200 if status_code < 400 else 502)

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
