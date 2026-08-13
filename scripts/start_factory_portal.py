#!/usr/bin/env python3
"""
Dedicated Azure Architecture Factory Portal Server
Serves factory projects, BRD intake API, and project management dashboard
"""

import base64
import html
import io
import json
import hmac
import logging
import os
import pathlib
import re
import struct
import sys
import threading
import time
import uuid
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, ThreadingHTTPServer, SimpleHTTPRequestHandler

UTC = timezone.utc


def _utcnow_iso() -> str:
    """Timezone-aware UTC ISO 8601 string (Python 3.13-compatible).

    Preserves the legacy `datetime.utcnow().isoformat() + 'Z'` output format.
    """
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

try:
    from telemetry import init_otel, get_tracer
except ModuleNotFoundError:
    # Telemetry module is optional; provide no-op shims so the portal runs
    # with stdlib only when scripts/ isn't on sys.path yet.
    def init_otel(*_args, **_kwargs):
        return False

    def get_tracer(_name="aaf-portal"):
        class _Noop:
            def start_as_current_span(self, *a, **kw):
                class _S:
                    def __enter__(self_inner):
                        return self_inner

                    def __exit__(self_inner, *a):
                        return False

                    def set_attribute(self_inner, *a, **kw):
                        pass

                    def set_status(self_inner, *a, **kw):
                        pass

                    def record_exception(self_inner, *a, **kw):
                        pass

                return _S()

        return _Noop()

try:
    from local_brd_runner import process_brd_document
except ModuleNotFoundError:
    from scripts.local_brd_runner import process_brd_document

try:
    import blob_sync
except ModuleNotFoundError:
    try:
        from scripts import blob_sync  # type: ignore[no-redef]
    except ModuleNotFoundError:
        class _BlobSyncStub:
            BLOB_ENABLED = False
            def sync_down(self, *a, **k): return {}
            def upload_project(self, *a, **k): return None
            def upload_feed(self, *a, **k): return None
            def upload_owners(self, *a, **k): return None
        blob_sync = _BlobSyncStub()  # type: ignore[assignment]

try:
    import copilot_runner
except ModuleNotFoundError:
    try:
        from scripts import copilot_runner  # type: ignore[no-redef]
    except ModuleNotFoundError:
        copilot_runner = None  # type: ignore[assignment]

try:
    from resilience import ResilientExecutor, RetryPolicy, get_circuit_breaker
except ModuleNotFoundError:
    try:
        from scripts.resilience import ResilientExecutor, RetryPolicy, get_circuit_breaker
    except ModuleNotFoundError:
        # Fallback: no resilience (graceful degradation)
        class _NoOpRetryPolicy:
            def __init__(self, *a, **kw):
                pass

        class _NoOpResilientExecutor:
            def __init__(self, *a, **kw): pass
            def execute(self, func, *args, **kwargs): return func(*args, **kwargs)
            def get_metrics(self): return {}
        RetryPolicy = _NoOpRetryPolicy  # type: ignore[assignment]
        ResilientExecutor = _NoOpResilientExecutor  # type: ignore[assignment]
        def get_circuit_breaker(name): return None  # type: ignore[return-value]


def _parse_multipart_form(content_type: str, body: bytes) -> dict:
    """Parse multipart/form-data body without the removed cgi module.
    Returns {field_name: {"data": bytes, "filename": str | None}}.
    """
    boundary = None
    for token in content_type.split(";"):
        token = token.strip()
        if token.lower().startswith("boundary="):
            boundary = token[9:].strip().strip('"')
            break
    if not boundary:
        return {}

    delimiter = ("--" + boundary).encode()
    fields: dict = {}

    for raw_part in body.split(delimiter)[1:]:
        if raw_part.startswith(b"--"):
            break  # end delimiter
        sep = b"\r\n\r\n" if b"\r\n\r\n" in raw_part else b"\n\n"
        if sep not in raw_part:
            continue
        header_bytes, data = raw_part.split(sep, 1)
        data = data.rstrip(b"\r\n")

        name: str | None = None
        filename: str | None = None
        for line in header_bytes.decode("utf-8", errors="replace").splitlines():
            if "Content-Disposition" in line:
                for tok in line.split(";"):
                    tok = tok.strip()
                    if tok.startswith("name="):
                        name = tok[5:].strip().strip('"')
                    elif tok.startswith("filename="):
                        filename = tok[9:].strip().strip('"')
        if name:
            fields[name] = {"data": data, "filename": filename}

    return fields


# Configuration
FACTORY_REPO_ROOT = pathlib.Path(__file__).parent.parent.resolve()
PORT = int(os.environ.get("FACTORY_PORTAL_PORT", "5501"))
BIND_ADDRESS = os.environ.get("FACTORY_PORTAL_BIND", "0.0.0.0")
MAX_REQUEST_BYTES = 1_000_000  # 1 MB intake payload limit
# BRD schema bounds (applied after size check)
MIN_BRD_CONTENT_CHARS = int(os.environ.get("AAFACTORY_MIN_BRD_CHARS", "50"))
MAX_BRD_CONTENT_CHARS = int(os.environ.get("AAFACTORY_MAX_BRD_CHARS", "800000"))
MAX_BRD_FILENAME_LEN = 120
# Intake rate limit (sliding window per caller key — UPN if authenticated, else IP)
INTAKE_RATE_PER_MIN = int(os.environ.get("AAFACTORY_INTAKE_RATE_PER_MIN", "6"))
INTAKE_RATE_WINDOW_SECONDS = 60
ALLOWED_ORIGIN = os.environ.get("FACTORY_PORTAL_ALLOWED_ORIGIN", f"http://localhost:{PORT}")
API_KEY_ENV = "FACTORY_PORTAL_API_KEY"
PORTAL_PATH_ALIASES = {"/portal", "/p"}
CSA_COPILOT_API_BASE = os.environ.get("CSA_COPILOT_API_BASE", "").strip().rstrip("/")
CSA_COPILOT_API_KEY = os.environ.get("CSA_COPILOT_API_KEY", "").strip()
CSA_COPILOT_TIMEOUT_SECONDS = int(os.environ.get("CSA_COPILOT_TIMEOUT_SECONDS", "20"))
SERVICE_START_EPOCH = time.time()
AAPAAS_ROOT = pathlib.Path(
    os.environ.get(
        "AAPAAS_ROOT",
        str(FACTORY_REPO_ROOT / "factory-templates" / "application-zone" / "aapaas"),
    )
)
AAPAAS_APP_PACKS_DIR = AAPAAS_ROOT / "app-packs"
AAPAAS_AGENT_PACKS_DIR = AAPAAS_ROOT / "agent-packs"
AAPAAS_CERTIFICATION_FILE = AAPAAS_ROOT / "certification" / "reports" / "certification-summary.generated.json"
AAPAAS_INSTANCES_DIR = AAPAAS_ROOT / "operations" / "instances"
AAPAAS_HEALTH_DIR = AAPAAS_ROOT / "operations" / "health"
AAPAAS_SCHEDULER_REPORT = AAPAAS_ROOT / "operations" / "scheduler" / "casewright-scheduler.generated.json"
APPLICATION_ZONE_RUNTIME_INSTANCES: dict[str, dict] = {}
# Optional: set this to a Teams Incoming Webhook URL to receive a notification
# whenever a user submits a token request.
TEAMS_WEBHOOK_URL = os.environ.get("FACTORY_PORTAL_TEAMS_WEBHOOK_URL", "")


def _portal_read_json(path: pathlib.Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _portal_app_pack_key(pack_id: str, version: str) -> str:
    return f"{pack_id}:{version}"


def _portal_agent_pack_key(agent_pack_id: str, version: str) -> str:
    return f"{agent_pack_id}:{version}"


def _portal_factory_template_url(path: pathlib.Path) -> str | None:
    templates_root = (FACTORY_REPO_ROOT / "factory-templates").resolve()
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(templates_root)
    except (OSError, ValueError):
        return None
    if not resolved.is_file():
        return None
    return f"/factory-templates/{relative.as_posix()}"


def _portal_add_documentation_link(links: list[dict], label: str, path: pathlib.Path) -> None:
    href = _portal_factory_template_url(path)
    if not href or any(item.get("href") == href for item in links):
        return
    links.append({"label": label, "href": href})


def _portal_documentation_path_candidates(value: str, manifest_path: pathlib.Path) -> list[pathlib.Path]:
    normalized = value.strip().replace("\\", "/").lstrip("/")
    if not normalized or "://" in normalized:
        return []
    candidates: list[pathlib.Path] = []
    if normalized.startswith("factory-templates/"):
        candidates.append(FACTORY_REPO_ROOT / normalized)
    else:
        candidates.extend([
            manifest_path.parent / normalized,
            FACTORY_REPO_ROOT / normalized,
        ])
    return candidates


def _portal_collect_manifest_documentation_links(manifest: dict, manifest_path: pathlib.Path) -> list[dict]:
    links: list[dict] = []

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "documentation":
                    docs = child if isinstance(child, list) else [child]
                    for doc in docs:
                        if not isinstance(doc, str):
                            continue
                        for candidate in _portal_documentation_path_candidates(doc, manifest_path):
                            if candidate.is_file():
                                _portal_add_documentation_link(links, "Docs", candidate)
                                break
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(manifest)
    return links


def _portal_app_pack_documentation_links(pack: dict, certification: dict) -> list[dict]:
    links: list[dict] = []
    manifest_path = pathlib.Path((pack.get("_portal") or {}).get("manifestPath", ""))
    if manifest_path:
        _portal_add_documentation_link(links, "Manifest", manifest_path)
        links.extend(_portal_collect_manifest_documentation_links(pack, manifest_path))

    pack_id = (pack.get("metadata") or {}).get("packId")
    report_name = certification.get("ReportPath") or (f"{pack_id}-certification.md" if pack_id else "")
    if report_name:
        _portal_add_documentation_link(
            links,
            "Certification",
            AAPAAS_ROOT / "certification" / "reports" / str(report_name),
        )
    return links


def _portal_agent_pack_documentation_links(agent_pack: dict) -> list[dict]:
    links: list[dict] = []
    manifest_path = pathlib.Path((agent_pack.get("_portal") or {}).get("manifestPath", ""))
    if manifest_path:
        _portal_add_documentation_link(links, "AgentPack manifest", manifest_path)

    metadata = agent_pack.get("metadata") or {}
    agent_pack_id = metadata.get("agentPackId")
    if agent_pack_id:
        _portal_add_documentation_link(
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
        _portal_add_documentation_link(links, "Parent manifest", parent_manifest)
        _portal_add_documentation_link(
            links,
            "Parent certification",
            AAPAAS_ROOT / "certification" / "reports" / f"{parent_pack_id}-certification.md",
        )

    _portal_add_documentation_link(links, "AgentPack schema", AAPAAS_ROOT / "docs" / "AGENTPACK_SCHEMA.md")
    return links


def _portal_load_app_packs() -> dict:
    registry: dict = {}
    roots = (
        (FACTORY_REPO_ROOT / "factory-templates" / "application-zone" / "packs", "aaf"),
        (AAPAAS_APP_PACKS_DIR, "aapaas"),
    )
    for root, source in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("**/manifest.json")):
            doc = _portal_read_json(path)
            if not isinstance(doc, dict):
                continue
            metadata = doc.get("metadata") or {}
            pack_id = metadata.get("packId")
            version = metadata.get("version")
            if not pack_id or not version:
                continue
            doc = dict(doc)
            doc["_portal"] = {"source": source, "manifestPath": str(path)}
            registry[_portal_app_pack_key(str(pack_id), str(version))] = doc
    return registry


def _portal_load_agent_packs() -> dict:
    registry: dict = {}
    roots = (
        (AAPAAS_AGENT_PACKS_DIR, "aapaas"),
    )
    for root, source in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("**/manifest.json")):
            doc = _portal_read_json(path)
            if not isinstance(doc, dict) or doc.get("kind") != "AgentPack":
                continue
            metadata = doc.get("metadata") or {}
            agent_pack_id = metadata.get("agentPackId")
            version = metadata.get("version")
            if not agent_pack_id or not version:
                continue
            doc = dict(doc)
            doc["_portal"] = {"source": source, "manifestPath": str(path)}
            registry[_portal_agent_pack_key(str(agent_pack_id), str(version))] = doc
    return registry


def _portal_load_aapaas_certifications() -> dict:
    records = _portal_read_json(AAPAAS_CERTIFICATION_FILE)
    if not isinstance(records, list):
        return {}
    result: dict = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        pack_id = item.get("PackId")
        version = item.get("Version")
        if pack_id and version:
            result[_portal_app_pack_key(str(pack_id), str(version))] = item
    return result


def _portal_load_aapaas_instances() -> list:
    instances: list = []
    if not AAPAAS_INSTANCES_DIR.exists():
        return instances
    for path in sorted(AAPAAS_INSTANCES_DIR.glob("*.instance.json")):
        doc = _portal_read_json(path)
        if not isinstance(doc, dict):
            continue
        metadata = doc.get("metadata") or {}
        runtime = doc.get("runtime") or {}
        azure = doc.get("azure") or {}
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


def _portal_load_aapaas_health() -> dict:
    result: dict = {}
    if not AAPAAS_HEALTH_DIR.exists():
        return result
    for path in sorted(AAPAAS_HEALTH_DIR.glob("*.health.generated.json")):
        doc = _portal_read_json(path)
        if not doc:
            continue
        checks = doc if isinstance(doc, list) else [doc]
        instance_id = checks[0].get("instanceId") if checks and isinstance(checks[0], dict) else None
        if instance_id:
            result[str(instance_id)] = {"checks": checks, "path": str(path)}
    return result


def _portal_load_aapaas_scheduler_report() -> dict:
    doc = _portal_read_json(AAPAAS_SCHEDULER_REPORT)
    return doc if isinstance(doc, dict) else {}


def _portal_build_pack_catalog() -> list:
    registry = _portal_load_app_packs()
    certs = _portal_load_aapaas_certifications()
    instances = _portal_load_aapaas_instances()
    grouped: dict = {}
    for pack in registry.values():
        pack_id = (pack.get("metadata") or {}).get("packId")
        if pack_id:
            grouped.setdefault(pack_id, []).append(pack)

    catalog = []
    for pack_id, versions in grouped.items():
        versions.sort(key=lambda item: (item.get("metadata") or {}).get("version", ""), reverse=True)
        latest = versions[0]
        metadata = latest.get("metadata") or {}
        compatibility = latest.get("compatibility") or {}
        inputs = latest.get("inputs") or {}
        key = _portal_app_pack_key(str(pack_id), str(metadata.get("version", "")))
        certification = certs.get(key, {})
        pack_instances = [
            item for item in instances
            if item.get("packId") == pack_id and item.get("packVersion") == metadata.get("version")
        ]
        catalog.append({
            "packId": pack_id,
            "displayName": metadata.get("displayName", pack_id),
            "latestVersion": metadata.get("version"),
            "status": metadata.get("status", "unknown"),
            "owner": metadata.get("owner", "unknown"),
            "supportTier": metadata.get("supportTier", "unknown"),
            "source": (latest.get("_portal") or {}).get("source", "aaf"),
            "certificationStatus": certification.get("Status"),
            "certificationWarnings": certification.get("Warnings", 0),
            "certificationBlockers": certification.get("Blockers", 0),
            "instanceCount": len(pack_instances),
            "instances": pack_instances,
            "supportedRegions": compatibility.get("supportedRegions", []),
            "requiredInputCount": len(inputs.get("required", [])),
            "requiredServices": compatibility.get("requiredServices", []),
            "documentationLinks": _portal_app_pack_documentation_links(latest, certification),
            "versions": [(item.get("metadata") or {}).get("version") for item in versions],
        })
    catalog.sort(key=lambda item: item.get("packId", ""))
    return catalog


def _portal_build_agent_pack_catalog() -> list:
    registry = _portal_load_agent_packs()
    grouped: dict = {}
    for pack in registry.values():
        agent_pack_id = (pack.get("metadata") or {}).get("agentPackId")
        if agent_pack_id:
            grouped.setdefault(agent_pack_id, []).append(pack)

    catalog = []
    for agent_pack_id, versions in grouped.items():
        versions.sort(key=lambda item: (item.get("metadata") or {}).get("version", ""), reverse=True)
        latest = versions[0]
        metadata = latest.get("metadata") or {}
        runtime = latest.get("runtime") or {}
        contract = latest.get("contract") or {}
        governance = latest.get("governance") or {}
        catalog.append({
            "offeringType": "agent-pack",
            "agentPackId": agent_pack_id,
            "displayName": metadata.get("displayName", agent_pack_id),
            "latestVersion": metadata.get("version"),
            "status": metadata.get("status", "unknown"),
            "owner": metadata.get("owner", "unknown"),
            "supportTier": metadata.get("supportTier", "unknown"),
            "source": (latest.get("_portal") or {}).get("source", "aapaas"),
            "parentAppPackId": metadata.get("parentAppPackId"),
            "canonicalSource": metadata.get("canonicalSource", "casewright"),
            "executionMode": runtime.get("executionMode", "unknown"),
            "runtimeEndpoint": runtime.get("defaultRuntimeEndpoint"),
            "toolCount": len(contract.get("tools", [])),
            "capabilities": contract.get("capabilities", []),
            "dataBoundary": governance.get("dataBoundary", ""),
            "certificationStatus": governance.get("certificationStatus"),
            "requiredEvidence": governance.get("requiredEvidence", []),
            "documentationLinks": _portal_agent_pack_documentation_links(latest),
            "versions": [(item.get("metadata") or {}).get("version") for item in versions],
        })
    catalog.sort(key=lambda item: item.get("agentPackId", ""))
    return catalog


def _portal_load_security_work_board() -> dict:
    cases_path = AAPAAS_ROOT / "evals" / "security-control-tower" / "cases.json"
    results_path = AAPAAS_ROOT / "evals" / "security-control-tower" / "evidence" / "results.json"
    cases = _portal_read_json(cases_path)
    results = _portal_read_json(results_path)
    if not isinstance(cases, list):
        cases = []
    if not isinstance(results, dict):
        results = {}

    result_by_case = {
        str(item.get("caseId")): item
        for item in results.get("results", [])
        if isinstance(item, dict) and item.get("caseId")
    }
    lane_order = ["orchestrator", "red", "blue", "green"]
    lane_labels = {
        "orchestrator": "Orchestrator",
        "red": "Red",
        "blue": "Blue",
        "green": "Green",
    }
    lanes = {
        lane: {
            "lane": lane,
            "label": lane_labels[lane],
            "items": [],
        }
        for lane in lane_order
    }

    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("caseId", ""))
        lane = str(case.get("lane", "orchestrator"))
        if lane not in lanes:
            lanes[lane] = {"lane": lane, "label": lane.title(), "items": []}
        approval = case.get("approval") if isinstance(case.get("approval"), dict) else {}
        classification = case.get("classification") if isinstance(case.get("classification"), dict) else {}
        actions = case.get("actions") if isinstance(case.get("actions"), list) else []
        evidence = case.get("evidence") if isinstance(case.get("evidence"), list) else []
        result = result_by_case.get(case_id, {})
        lanes[lane]["items"].append({
            "caseId": case_id,
            "request": case.get("request", ""),
            "playbook": classification.get("playbook", ""),
            "risk": classification.get("risk", ""),
            "scope": classification.get("scope", ""),
            "approvalState": approval.get("state", ""),
            "requiredFor": approval.get("requiredFor", []),
            "actionModes": sorted({
                str(action.get("mode", ""))
                for action in actions
                if isinstance(action, dict) and action.get("mode")
            }),
            "evidenceTypes": [
                str(item.get("type", ""))
                for item in evidence
                if isinstance(item, dict) and item.get("type")
            ],
            "evalPassed": bool(result.get("passed")),
            "failures": result.get("failures", []),
        })

    return {
        "updated_at": _utcnow_iso(),
        "gate": results.get("gate", "UNKNOWN"),
        "caseCount": len(cases),
        "passedCount": int(results.get("passedCount", 0) or 0),
        "failedCount": int(results.get("failedCount", 0) or 0),
        "blockingChecks": results.get("blockingChecks", []),
        "lanes": [lanes[lane] for lane in lane_order if lane in lanes],
        "scorecardHref": "/factory-templates/application-zone/aapaas/evals/security-control-tower/evidence/scorecard.md",
        "evalReadmeHref": "/factory-templates/application-zone/aapaas/evals/security-control-tower/README.md",
    }


def _portal_load_security_tool_integrations() -> dict:
    integrations_path = AAPAAS_ROOT / "evals" / "security-control-tower" / "tool-integrations.json"
    integrations = _portal_read_json(integrations_path)
    if not isinstance(integrations, dict):
        integrations = {}
    return {
        "updated_at": _utcnow_iso(),
        "readOnlySources": integrations.get("readOnlySources", []),
        "draftOnlyOutputs": integrations.get("draftOnlyOutputs", []),
        "safetyControls": integrations.get("safetyControls", []),
        "contractHref": "/factory-templates/application-zone/aapaas/evals/security-control-tower/tool-integrations.json",
    }


def _portal_load_security_approval_workflows() -> dict:
    workflows_path = AAPAAS_ROOT / "evals" / "security-control-tower" / "approval-workflows.json"
    workflows = _portal_read_json(workflows_path)
    if not isinstance(workflows, dict):
        workflows = {}
    return {
        "updated_at": _utcnow_iso(),
        "approvalWorkflows": workflows.get("approvalWorkflows", []),
        "requiredSensitiveActions": workflows.get("requiredSensitiveActions", []),
        "approvalPrinciples": workflows.get("approvalPrinciples", []),
        "contractHref": "/factory-templates/application-zone/aapaas/evals/security-control-tower/approval-workflows.json",
    }


def _portal_load_security_pilot_readiness() -> dict:
    readiness_path = AAPAAS_ROOT / "evals" / "security-control-tower" / "pilot-readiness.json"
    readiness = _portal_read_json(readiness_path)
    if not isinstance(readiness, dict):
        readiness = {}
    return {
        "updated_at": _utcnow_iso(),
        "pilotReadiness": readiness.get("pilotReadiness", {}),
        "readinessChecks": readiness.get("readinessChecks", []),
        "pilotControls": readiness.get("pilotControls", []),
        "contractHref": "/factory-templates/application-zone/aapaas/evals/security-control-tower/pilot-readiness.json",
    }


def _portal_load_security_connector_pilot() -> dict:
    pilot_path = AAPAAS_ROOT / "evals" / "security-control-tower" / "connector-pilot.json"
    pilot = _portal_read_json(pilot_path)
    if not isinstance(pilot, dict):
        pilot = {}
    return {
        "updated_at": _utcnow_iso(),
        "connectorPilot": pilot.get("connectorPilot", {}),
        "connectors": pilot.get("connectors", []),
        "pilotPrerequisites": pilot.get("pilotPrerequisites", []),
        "rolloutControls": pilot.get("rolloutControls", []),
        "contractHref": "/factory-templates/application-zone/aapaas/evals/security-control-tower/connector-pilot.json",
    }


def _portal_load_security_pilot_evidence() -> dict:
    evidence_path = AAPAAS_ROOT / "evals" / "security-control-tower" / "pilot-evidence.json"
    evidence = _portal_read_json(evidence_path)
    if not isinstance(evidence, dict):
        evidence = {}
    return {
        "updated_at": _utcnow_iso(),
        "evidenceCapture": evidence.get("evidenceCapture", {}),
        "captureItems": evidence.get("captureItems", []),
        "evidenceControls": evidence.get("evidenceControls", []),
        "contractHref": "/factory-templates/application-zone/aapaas/evals/security-control-tower/pilot-evidence.json",
    }


def _portal_list_pack_versions(pack_id: str) -> list:
    registry = _portal_load_app_packs()
    versions = [
        item for item in registry.values()
        if (item.get("metadata") or {}).get("packId") == pack_id
    ]
    versions.sort(key=lambda item: (item.get("metadata") or {}).get("version", ""), reverse=True)
    return versions


def _portal_get_pack_or_none(pack_id: str, version: str) -> dict | None:
    return _portal_load_app_packs().get(_portal_app_pack_key(pack_id, version))


def _portal_parse_json_payload(handler) -> tuple[dict | None, bool]:
    content_length = handler._safe_content_length()
    if content_length is None:
        return None, False
    try:
        body = handler.rfile.read(content_length).decode("utf-8")
        payload = json.loads(body) if body else {}
    except Exception as exc:
        handler._send_json({"error": f"Invalid request: {exc}"}, 400)
        return None, False
    if not isinstance(payload, dict):
        handler._send_json({"error": "Request body must be a JSON object"}, 400)
        return None, False
    return payload, True


def _portal_validate_app_pack_inputs(payload: dict) -> dict:
    pack_id = str(payload.get("packId", "") or "").strip()
    version = str(payload.get("version", "") or "").strip()
    profile = str(payload.get("profile", "dev") or "dev").strip()
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    errors: list[dict] = []
    warnings: list[dict] = []

    if not pack_id:
        errors.append({"field": "packId", "message": "packId is required"})
    if not version:
        errors.append({"field": "version", "message": "version is required"})

    pack = _portal_get_pack_or_none(pack_id, version) if pack_id and version else None
    if not pack:
        errors.append({
            "field": "packId",
            "message": f"App Pack version not found: {pack_id}@{version}",
        })
        return {
            "ok": False,
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "pack": {"packId": pack_id, "version": version},
        }

    metadata = pack.get("metadata") or {}
    deployment = pack.get("deployment") or {}
    runtime_profiles = deployment.get("runtimeProfiles") or []
    if runtime_profiles and profile not in runtime_profiles:
        errors.append({
            "field": "profile",
            "message": f"profile must be one of: {', '.join(map(str, runtime_profiles))}",
        })

    for spec in (pack.get("inputs") or {}).get("required", []):
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", "") or "").strip()
        expected_type = str(spec.get("type", "string") or "string")
        value = inputs.get(name)
        if value in (None, ""):
            errors.append({"field": f"inputs.{name}", "message": f"{name} is required"})
            continue
        if expected_type == "enum":
            allowed = [str(item) for item in spec.get("allowedValues", [])]
            if allowed and str(value) not in allowed:
                errors.append({
                    "field": f"inputs.{name}",
                    "message": f"{name} must be one of: {', '.join(allowed)}",
                })
        elif expected_type == "object":
            if not isinstance(value, dict):
                errors.append({"field": f"inputs.{name}", "message": f"{name} must be an object"})
                continue
            for required_field in spec.get("requiredFields", []):
                if value.get(required_field) in (None, ""):
                    errors.append({
                        "field": f"inputs.{name}.{required_field}",
                        "message": f"{name}.{required_field} is required",
                    })
        elif expected_type == "integer" and not isinstance(value, int):
            errors.append({"field": f"inputs.{name}", "message": f"{name} must be an integer"})
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append({"field": f"inputs.{name}", "message": f"{name} must be a boolean"})
        elif expected_type == "string" and not isinstance(value, str):
            errors.append({"field": f"inputs.{name}", "message": f"{name} must be a string"})

    runtime = inputs.get("runtime")
    if runtime is not None and not isinstance(runtime, dict):
        errors.append({"field": "inputs.runtime", "message": "runtime must be an object when provided"})
    elif isinstance(runtime, dict):
        base_url = str(runtime.get("baseUrl", "") or "").strip()
        if base_url and not re.match(r"^https?://", base_url):
            errors.append({"field": "inputs.runtime.baseUrl", "message": "runtime baseUrl must start with http:// or https://"})

    return {
        "ok": not errors,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "pack": {
            "packId": pack_id,
            "version": version,
            "displayName": metadata.get("displayName", pack_id),
            "source": (pack.get("_portal") or {}).get("source", "aaf"),
            "profile": profile,
        },
    }


def _portal_summarize_instance(instance: dict) -> dict:
    pack = instance.get("pack") or {}
    runtime = instance.get("runtime") or {}
    return {
        "instanceId": instance.get("instanceId"),
        "packId": pack.get("packId"),
        "packVersion": pack.get("version"),
        "displayName": instance.get("displayName"),
        "profile": instance.get("profile"),
        "status": instance.get("status"),
        "createdAt": instance.get("createdAt"),
        "runtimeConnected": bool(runtime.get("baseUrl")),
        "runtimeBaseUrl": runtime.get("baseUrl"),
    }


class _SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter.

    Thread-safe. Keeps a deque of recent hit timestamps per caller key and
    rejects once the window count exceeds `limit`. Memory is bounded by the
    number of active callers over any given window.
    """

    def __init__(self, limit: int, window_seconds: int):
        self._limit = max(1, int(limit))
        self._window = max(1, int(window_seconds))
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds).

        retry_after_seconds is 0 when allowed; otherwise the number of seconds
        the caller should wait before the next slot frees up.
        """
        if not key:
            return True, 0
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                bucket = deque()
                self._hits[key] = bucket
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._limit:
                retry = max(1, int(self._window - (now - bucket[0])))
                return False, retry
            bucket.append(now)
            return True, 0


_INTAKE_LIMITER = _SlidingWindowRateLimiter(
    limit=INTAKE_RATE_PER_MIN,
    window_seconds=INTAKE_RATE_WINDOW_SECONDS,
)


# ---------------------------------------------------------------------------
# Readiness-probe helpers
# ---------------------------------------------------------------------------
READINESS_BLOB_CACHE_TTL_SECONDS = 30
_READINESS_BLOB_CACHE: dict = {"expiresAt": 0.0, "value": None}
_READINESS_BLOB_CACHE_LOCK = threading.Lock()


def _probe_intake_writable(intake_dir: pathlib.Path) -> bool:
    """Return True if intake_dir can be created, written to, and cleaned up."""
    try:
        intake_dir.mkdir(parents=True, exist_ok=True)
        probe = intake_dir / f".readiness-probe-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _otel_enabled() -> bool:
    """Return True if the OpenTelemetry exporter was successfully initialized."""
    try:
        import telemetry  # local module
        return bool(getattr(telemetry, "telemetry_enabled", False))
    except Exception:
        return False


def _probe_blob_storage_cached() -> dict:
    """HEAD the configured blob container. Result cached for 30s to keep the
    readiness probe cheap and avoid hammering storage on every Kubernetes tick.
    """
    now = time.monotonic()
    with _READINESS_BLOB_CACHE_LOCK:
        cached = _READINESS_BLOB_CACHE.get("value")
        if cached is not None and _READINESS_BLOB_CACHE["expiresAt"] > now:
            return cached

    result: dict = {"ok": False, "checkedAt": _utcnow_iso()}
    try:
        import urllib.request
        account = os.environ.get("FACTORY_PORTAL_BLOB_ACCOUNT", "").strip()
        container = os.environ.get("FACTORY_PORTAL_BLOB_CONTAINER", "portal-state").strip() or "portal-state"
        if not account:
            result["error"] = "no account configured"
        else:
            # Unauthenticated HEAD — we only care that the endpoint reachable.
            # A 401/403 still proves storage DNS + TLS + TCP are healthy.
            url = f"https://{account}.blob.core.windows.net/{container}?restype=container"
            req = urllib.request.Request(url, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    result["ok"] = True
                    result["statusCode"] = resp.status
            except urllib.error.HTTPError as http_exc:
                # 401/403 = reachable but we're not authorized (expected).
                if http_exc.code in (401, 403, 404):
                    result["ok"] = True
                    result["statusCode"] = http_exc.code
                else:
                    result["statusCode"] = http_exc.code
                    result["error"] = f"HTTP {http_exc.code}"
    except Exception as exc:  # noqa: BLE001 - probe must never crash caller
        result["error"] = f"{type(exc).__name__}: {exc}"

    with _READINESS_BLOB_CACHE_LOCK:
        _READINESS_BLOB_CACHE["value"] = result
        _READINESS_BLOB_CACHE["expiresAt"] = now + READINESS_BLOB_CACHE_TTL_SECONDS
    return result


# Optional per-deployment project visibility allowlist. Comma-separated slugs.
# When set, the portal only exposes (feed + file routes) the listed projects.
# When unset or empty, all projects under projects/ are visible (local default).
# Use this on the hosted/external portal to limit which projects are public.
_visible_raw = os.environ.get("FACTORY_PORTAL_VISIBLE_SLUGS", "").strip()
VISIBLE_SLUGS: frozenset[str] | None = (
    frozenset(s.strip() for s in _visible_raw.split(",") if s.strip())
    if _visible_raw
    else None
)


def _is_slug_visible(slug: str) -> bool:
    """Return True if the slug is allowed by the visibility allowlist.

    When no allowlist is configured (VISIBLE_SLUGS is None), everything is
    visible (local dev default). When configured, only listed slugs pass.
    """
    if VISIBLE_SLUGS is None:
        return True
    return bool(slug) and slug in VISIBLE_SLUGS


# ── Per-user ownership (Entra ID via Container Apps Easy Auth) ───────────────
#
# When FACTORY_PORTAL_AUTH_MODE=entra, the portal reads the Easy Auth headers
# (X-MS-CLIENT-PRINCIPAL-NAME = the user's UPN) and filters every project the
# user can see based on the owner sidecar file: .portal-owners.json at repo
# root. Shape:
#   {
#     "admins": ["admin@contoso.com"],
#     "projects": {
#       "slug-a": ["alice@contoso.com"],
#       "slug-b": ["bob@contoso.com", "carol@contoso.com"]
#     }
#   }
# Additional admins can be provided via FACTORY_PORTAL_ADMINS (comma list).
# Admins always see every project. When AUTH_MODE is not 'entra', all users
# see everything (local dev default — the allowlist above still applies if set).

AUTH_MODE = os.environ.get("FACTORY_PORTAL_AUTH_MODE", "").strip().lower()
_allow_local_repo_default = "1" if AUTH_MODE in {"", "none"} else "0"
ALLOW_LOCAL_REPO_INTAKE = os.environ.get(
    "FACTORY_PORTAL_ALLOW_LOCAL_REPO_INTAKE", _allow_local_repo_default
).strip().lower() in {"1", "true", "yes", "on"}
# Owners data source — in order of precedence:
#   1. FACTORY_PORTAL_OWNERS_JSON : inline JSON (e.g. mounted via Container App
#      secret env var). Read-only; auto-stamping submitters is skipped.
#   2. FACTORY_PORTAL_OWNERS_FILE : path override (e.g. Azure Files mount).
#   3. <repo root>/.portal-owners.json : default for local dev and image seed.
_OWNERS_JSON_ENV = os.environ.get("FACTORY_PORTAL_OWNERS_JSON", "").strip()
OWNERS_FILE = pathlib.Path(
    os.environ.get("FACTORY_PORTAL_OWNERS_FILE")
    or (FACTORY_REPO_ROOT / ".portal-owners.json")
)
_env_admins = os.environ.get("FACTORY_PORTAL_ADMINS", "")
_ENV_ADMINS: frozenset[str] = frozenset(
    a.strip().lower() for a in _env_admins.split(",") if a.strip()
)

# Optional tenant allowlist. When set, only users whose Entra token 'tid' claim
# (home tenant) is in this list may access the portal — used with a
# multi-tenant app registration to accept e.g. any Microsoft employee while
# still rejecting guests from other tenants.
# Default: empty → no tenant restriction (single-tenant deployments rely on
# Easy Auth's own issuer check to enforce the tenant).
_allowed_tenants_raw = os.environ.get("FACTORY_PORTAL_ALLOWED_TENANTS", "").strip()
ALLOWED_TENANTS: frozenset[str] | None = (
    frozenset(t.strip().lower() for t in _allowed_tenants_raw.split(",") if t.strip())
    if _allowed_tenants_raw
    else None
)


def _load_owners() -> dict:
    """Load owners data; return an empty structure on any error.

    Sources in order: FACTORY_PORTAL_OWNERS_JSON env var (inline JSON, or
    base64-encoded JSON — auto-detected), then OWNERS_FILE on disk.
    """
    if _OWNERS_JSON_ENV:
        raw_text = _OWNERS_JSON_ENV
        # If the value doesn't look like JSON, try base64-decoding it.
        if not raw_text.lstrip().startswith("{"):
            try:
                raw_text = base64.b64decode(raw_text, validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                logger.warning("FACTORY_PORTAL_OWNERS_JSON b64 decode failed: %s", exc)
                raw_text = _OWNERS_JSON_ENV
        try:
            raw = json.loads(raw_text)
            if isinstance(raw, dict):
                return raw
        except json.JSONDecodeError as exc:
            logger.warning("FACTORY_PORTAL_OWNERS_JSON is not valid JSON: %s", exc)
    try:
        if OWNERS_FILE.is_file():
            raw = json.loads(OWNERS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", OWNERS_FILE.name, exc)
    return {"admins": [], "projects": {}}


def _save_owners(data: dict) -> None:
    if _OWNERS_JSON_ENV:
        # Secret-backed mode is read-only from the container; auto-stamping
        # submitters is a no-op. Admins must update the secret out-of-band.
        logger.info(
            "Skipping owners write: FACTORY_PORTAL_OWNERS_JSON is set (read-only mode)"
        )
        return
    try:
        OWNERS_FILE.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Failed to write %s: %s", OWNERS_FILE.name, exc)


def _is_admin(user: str | None) -> bool:
    if not user:
        return False
    u = user.strip().lower()
    if u in _ENV_ADMINS:
        return True
    owners = _load_owners()
    for a in owners.get("admins") or []:
        if isinstance(a, str) and a.strip().lower() == u:
            return True
    return False


def _project_owners(slug: str) -> set[str]:
    owners = _load_owners().get("projects") or {}
    raw = owners.get(slug) or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(x).strip().lower() for x in raw if str(x).strip()}


def _user_can_see_project(slug: str, user: str | None) -> bool:
    """Apply both the VISIBLE_SLUGS allowlist and per-user ownership rules."""
    if not _is_slug_visible(slug):
        return False
    if AUTH_MODE != "entra":
        return True  # local dev / unauthenticated hosted = no per-user filter
    if _is_admin(user):
        return True
    if not user:
        return False
    return user.strip().lower() in _project_owners(slug)


MAX_PREVIEW_BYTES = 512_000
TEXT_PREVIEW_SUFFIXES = {
    ".md", ".txt", ".py", ".json", ".yaml", ".yml", ".bicep", ".toml", ".ini",
    ".cfg", ".csv", ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".sh", ".ps1",
    ".xml", ".drawio",
}

# Entra ID (Azure AD) OAuth 2.0 configuration
# Set these env vars to enable Entra ID auth on mutation endpoints.
# When unset, Entra ID auth is skipped (local development mode).
ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID", "").strip()
ENTRA_CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID", "").strip()  # App registration Application (client) ID
ENTRA_AUDIENCE = os.environ.get("ENTRA_AUDIENCE", "").strip() or ENTRA_CLIENT_ID  # Defaults to client ID

# When the portal runs behind Azure Container Apps / App Service EasyAuth,
# the ingress strips any caller-supplied X-MS-CLIENT-PRINCIPAL* headers and
# replaces them with values from the validated session. Setting this env var
# tells the portal it is safe to trust those headers as proof of an
# authenticated Entra user (browser UI flow — no Bearer token required).
# NEVER enable this when the portal is exposed without EasyAuth in front.
TRUST_EASYAUTH_HEADERS = os.environ.get("TRUST_EASYAUTH_HEADERS", "").strip().lower() in ("1", "true", "yes")

# Optional per-endpoint allowlist for BRD intake mutations. Comma-separated
# list of principals (UPN/email or object id). Matches against the
# `preferred_username` and `oid` claims on the authenticated caller.
# When empty, any authenticated user may submit BRDs (Entra/EasyAuth still gates sign-in).
def _parse_principal_allowlist(raw: str) -> set[str]:
    return {p.strip().lower() for p in (raw or "").split(",") if p.strip()}

BRD_INTAKE_ALLOWED_PRINCIPALS = _parse_principal_allowlist(
    os.environ.get("BRD_INTAKE_ALLOWED_PRINCIPALS", "")
)

# File-backed overlay for the allowlist so admins can edit it from the portal
# without redeploying. The file is merged with BRD_INTAKE_ALLOWED_PRINCIPALS;
# removing an env-baked entry requires changing the env var (env is the seed).
BRD_ALLOWLIST_FILE = pathlib.Path(
    os.environ.get("BRD_INTAKE_ALLOWLIST_FILE")
    or (FACTORY_REPO_ROOT / ".brd-allowlist.json")
)


def _load_brd_allowlist_file() -> set[str]:
    try:
        if BRD_ALLOWLIST_FILE.is_file():
            raw = json.loads(BRD_ALLOWLIST_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return {str(x).strip().lower() for x in raw if str(x).strip()}
            if isinstance(raw, dict) and isinstance(raw.get("principals"), list):
                return {str(x).strip().lower() for x in raw["principals"] if str(x).strip()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", BRD_ALLOWLIST_FILE.name, exc)
    return set()


def _save_brd_allowlist_file(principals: set[str]) -> None:
    try:
        BRD_ALLOWLIST_FILE.write_text(
            json.dumps({"principals": sorted(principals)}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to write %s: %s", BRD_ALLOWLIST_FILE.name, exc)


def _current_brd_allowlist() -> set[str]:
    """Effective allowlist = env seed ∪ file overlay."""
    return BRD_INTAKE_ALLOWED_PRINCIPALS | _load_brd_allowlist_file()


# ── Entra ID JWT validation (stdlib + minimal base64 decode) ─────────────────

class _JwksCache:
    """Fetches and caches Microsoft OIDC signing keys."""

    def __init__(self, tenant_id: str, ttl: int = 3600):
        self._oidc_url = (
            f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
        )
        self._keys: dict[str, dict] = {}
        self._expires_at: float = 0
        self._ttl = ttl
        self._lock = threading.Lock()

    def get_key(self, kid: str) -> dict | None:
        with self._lock:
            if time.monotonic() >= self._expires_at:
                self._refresh()
            return self._keys.get(kid)

    def _refresh(self):
        try:
            oidc = json.loads(urlopen(Request(self._oidc_url), timeout=10).read())
            jwks_uri = oidc["jwks_uri"]
            jwks = json.loads(urlopen(Request(jwks_uri), timeout=10).read())
            self._keys = {k["kid"]: k for k in jwks.get("keys", [])}
            self._expires_at = time.monotonic() + self._ttl
        except Exception:
            self._expires_at = time.monotonic() + min(300, self._ttl)
            raise
def _rsa_verify(n_b64: str, e_b64: str, signature: bytes, message: bytes) -> bool:
    """Verify RSA PKCS#1 v1.5 signature using stdlib only.
    Constructs the public key from JWK n/e and performs raw RSA.
    """
    n = _int_from_bytes(_b64url_decode(n_b64))
    e = _int_from_bytes(_b64url_decode(e_b64))
    sig_int = _int_from_bytes(signature)
    # RSA public operation: sig^e mod n
    decrypted = pow(sig_int, e, n)
    # Convert back to bytes (same length as modulus)
    key_len = (n.bit_length() + 7) // 8
    em = decrypted.to_bytes(key_len, byteorder="big")
    # PKCS#1 v1.5: 0x00 0x01 [padding 0xff...] 0x00 [DigestInfo + hash]
    # We extract the hash from the end and compare
    import hashlib
    expected_hash = hashlib.sha256(message).digest()
    # DigestInfo prefix for SHA-256 (DER encoded)
    digest_info_prefix = bytes.fromhex(
        "3031300d060960864801650304020105000420"
    )
    expected_suffix = digest_info_prefix + expected_hash
    # Verify padding structure
    if not em.startswith(b"\x00\x01"):
        return False
    # Find 0x00 separator after padding
    sep_idx = em.index(b"\x00", 2)
    padding = em[2:sep_idx]
    if not all(b == 0xFF for b in padding):
        return False
    actual_suffix = em[sep_idx + 1:]
    return actual_suffix == expected_suffix


def _validate_entra_token(auth_header: str, jwks_cache: _JwksCache) -> dict | str:
    """Validate an Entra ID bearer token.
    Returns the decoded claims dict on success, or an error string on failure.
    """
    if not auth_header.lower().startswith("bearer "):
        return "Authorization header must use Bearer scheme"

    token = auth_header[7:].strip()
    parts = token.split(".")
    if len(parts) != 3:
        return "Malformed JWT"

    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
        signature = _b64url_decode(parts[2])
    except Exception:
        return "Failed to decode JWT"

    # Verify algorithm
    alg = header.get("alg", "")
    if alg != "RS256":
        return f"Unsupported algorithm: {alg}"

    # Look up signing key
    kid = header.get("kid", "")
    key = jwks_cache.get_key(kid)
    if not key:
        return "Signing key not found"

    # Verify signature
    message = f"{parts[0]}.{parts[1]}".encode("ascii")
    if not _rsa_verify(key["n"], key["e"], signature, message):
        return "Invalid token signature"

    # Verify claims
    now = time.time()
    if payload.get("exp", 0) < now:
        return "Token expired"
    if payload.get("nbf", 0) > now + 300:  # 5 min clock skew
        return "Token not yet valid"

    # Verify audience
    token_aud = payload.get("aud", "")
    if isinstance(token_aud, list):
        if ENTRA_AUDIENCE not in token_aud:
            return "Invalid audience"
    elif token_aud != ENTRA_AUDIENCE:
        return "Invalid audience"

    # Verify issuer (v2.0 endpoint)
    expected_issuer = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0"
    if payload.get("iss") != expected_issuer:
        return "Invalid issuer"

    return payload


# ── Issued-token helpers ─────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _notify_teams_token_request(req_id: str, sub: str, reason: str) -> None:
    """Fire-and-forget Teams Incoming Webhook notification for a new token request.

    Requires the FACTORY_PORTAL_TEAMS_WEBHOOK_URL env var to be set.
    Failures are logged but never surface to the caller.
    """
    if not TEAMS_WEBHOOK_URL:
        return
    import threading
    def _send():
        try:
            portal_url = f"http://localhost:{PORT}/factory-portal.html"
            card = {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "🔑 New Portal Token Request",
                                "weight": "Bolder",
                                "size": "Medium",
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {"title": "From",   "value": sub or "(unknown)"},
                                    {"title": "Reason", "value": reason or "(none provided)"},
                                    {"title": "ID",     "value": req_id},
                                ],
                            },
                            {
                                "type": "TextBlock",
                                "text": f"Open the admin panel on the portal to review and issue a token.",
                                "wrap": True,
                                "color": "Accent",
                            },
                        ],
                        "actions": [{
                            "type": "Action.OpenUrl",
                            "title": "Open Admin Panel",
                            "url": portal_url,
                        }],
                    },
                }],
            }
            data = json.dumps(card).encode("utf-8")
            req = Request(TEAMS_WEBHOOK_URL, data=data,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=8) as resp:  # noqa: S310
                logger.info("Teams notification sent for token request %s: HTTP %s", req_id, resp.status)
        except Exception as exc:
            logger.warning("Teams notification failed for token request %s: %s", req_id, exc)
    threading.Thread(target=_send, daemon=True).start()


def _issue_token(sub: str, ttl_seconds: int, max_uses: int, purpose: str) -> dict:
    """Create a signed, time-limited, usage-counted access token.

    Token format: <b64url(json_payload)>.<hmac_sha256_hex>
    The master FACTORY_PORTAL_API_KEY is the signing secret.
    Returns a dict with keys: token, jti, sub, exp, max_uses, purpose.
    Raises ValueError if the master key is not set.
    """
    master_key = os.environ.get(API_KEY_ENV, "").strip()
    if not master_key:
        raise ValueError("FACTORY_PORTAL_API_KEY must be set to issue tokens")

    now = time.time()
    jti = uuid.uuid4().hex
    exp = 0 if ttl_seconds == 0 else int(now + ttl_seconds)  # 0 = never expires
    payload = {
        "jti": jti,
        "sub": sub,
        "iat": int(now),
        "exp": exp,
        "max_uses": max_uses,
        "purpose": purpose,
    }
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(master_key.encode(), encoded_payload.encode(), "sha256").hexdigest()
    token = f"{encoded_payload}.{sig}"

    with _ISSUED_TOKENS_LOCK:
        _ISSUED_TOKENS[jti] = {
            "uses": 0,
            "max_uses": max_uses,
            "exp": exp,
            "sub": sub,
            "purpose": purpose,
        }

    logger.info("Issued token: jti=%s sub=%s purpose=%s max_uses=%s exp=%s",
                jti, sub, purpose, max_uses if max_uses > 0 else "unlimited", exp)
    return {"token": token, "jti": jti, "sub": sub, "exp": exp,
            "max_uses": max_uses, "purpose": purpose}


def _validate_issued_token(token: str) -> dict | str | None:
    """Validate an issued token. Returns claims dict on success, error string on failure."""
    master_key = os.environ.get(API_KEY_ENV, "").strip()
    if not master_key:
        return "No master key configured"

    if token.count(".") != 1:
        return None  # Not an issued-token format — let caller try master key

    encoded_payload, provided_sig = token.split(".", 1)
    expected_sig = hmac.new(master_key.encode(), encoded_payload.encode(), "sha256").hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        return "Invalid token signature"

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except Exception:
        return "Failed to decode token payload"

    token_exp = payload.get("exp", 0)
    if token_exp != 0 and token_exp < time.time():
        return "Token expired"

    jti = payload.get("jti", "")
    max_uses = payload.get("max_uses", 0)

    with _ISSUED_TOKENS_LOCK:
        if jti not in _ISSUED_TOKENS:
            # Server restarted — re-register; counter resets to 0 (acceptable trade-off)
            _ISSUED_TOKENS[jti] = {
                "uses": 0,
                "max_uses": max_uses,
                "exp": payload.get("exp", 0),
                "sub": payload.get("sub", ""),
                "purpose": payload.get("purpose", ""),
            }
        entry = _ISSUED_TOKENS[jti]
        if max_uses > 0 and entry["uses"] >= max_uses:
            return f"Token usage limit reached ({max_uses} uses)"
        entry["uses"] += 1
        current_uses = entry["uses"]

    logger.info("Token used: jti=%s sub=%s purpose=%s uses=%d/%s",
                jti, payload.get("sub"), payload.get("purpose"),
                current_uses, max_uses if max_uses > 0 else "unlimited")
    return payload


# Initialize JWKS cache (only when Entra ID is configured)
_jwks_cache: _JwksCache | None = None
if ENTRA_TENANT_ID and ENTRA_CLIENT_ID:
    _jwks_cache = _JwksCache(ENTRA_TENANT_ID)

# Thread-safe run tracking
RUNS = {}
RUNS_LOCK = threading.Lock()

# ── Self-healing resilience configuration ────────────────────────────────────
# Retry policy for transient BRD processing failures (I/O, timeouts, etc.)
_BRD_RETRY_POLICY = RetryPolicy(
    max_attempts=int(os.environ.get("AAFACTORY_BRD_MAX_RETRIES", "3")),
    initial_backoff_sec=float(os.environ.get("AAFACTORY_BRD_BACKOFF_SEC", "2.0")),
    max_backoff_sec=float(os.environ.get("AAFACTORY_BRD_MAX_BACKOFF_SEC", "60.0")),
)

# Resilient executor for BRD processing with circuit breaker
_BRD_EXECUTOR = ResilientExecutor(
    name="brd-processor",
    retry_policy=_BRD_RETRY_POLICY,
    circuit_breaker=get_circuit_breaker("brd-processor"),
    transient_errors_only=True,
)

# ── Run persistence (crash-safe) ──────────────────────────────────────────────
# Runs are snapshotted to disk after every status transition so a container
# restart does not orphan in-flight or recently-finished work. The file is
# ignored by git (see .gitignore). Active runs (queued/running) are marked
# "interrupted" on startup so the UI can surface them instead of pretending
# they are still executing.
_RUNS_STATE_PATH = pathlib.Path(os.environ.get(
    "AAFACTORY_RUNS_STATE",
    str(pathlib.Path(__file__).resolve().parent.parent / "logs" / "portal-runs.state.json"),
))
_RUNS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _persist_runs_unlocked() -> None:
    """Write RUNS to disk atomically. Caller must hold RUNS_LOCK."""
    try:
        tmp = _RUNS_STATE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(RUNS, default=str), encoding="utf-8")
        tmp.replace(_RUNS_STATE_PATH)
    except Exception:  # noqa: BLE001
        # Persistence is best-effort — never break a live request because
        # the disk is full or the path is unwritable.
        pass


def persist_runs() -> None:
    """Acquire the lock and snapshot RUNS to disk."""
    with RUNS_LOCK:
        _persist_runs_unlocked()


def _restore_runs_on_startup() -> None:
    """Load RUNS from disk at boot. Mark any queued/running entries as interrupted."""
    if not _RUNS_STATE_PATH.exists():
        return
    try:
        data = json.loads(_RUNS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    if not isinstance(data, dict):
        return
    now = _utcnow_iso()
    with RUNS_LOCK:
        for run_id, run in data.items():
            if not isinstance(run, dict):
                continue
            if run.get("status") in {"queued", "running"}:
                run["status"] = "interrupted"
                run["finishedAt"] = now
                run["stderr"] = (run.get("stderr") or "") + "\n[portal restart] run interrupted by container restart"
            RUNS[run_id] = run
        _persist_runs_unlocked()


def _build_agent_foundry_plan(source_type: str, title: str, content: str) -> dict:
    """Build a deterministic portal execution plan from user-provided source text."""
    source_label = {
        "brd-prd": "BRD/PRD",
        "architecture-markdown": "architecture markdown",
        "architecture-mermaid": "Mermaid architecture diagram",
        "architecture-drawio": "draw.io architecture diagram",
        "architecture-visio": "Visio architecture diagram",
        "learning-plan": "learning plan",
    }.get(source_type, source_type)
    diagram_source_types = {"architecture-markdown", "architecture-mermaid", "architecture-drawio", "architecture-visio"}
    seed_lines = [line.strip(" #-\t") for line in content.splitlines() if line.strip()]
    goals = seed_lines[:5] or [title]
    owner_agents = [
        "Azure AI Application Orchestrator",
        "Application Planning Companion Agent",
        "Configuration Environment Contract Agent",
        "Security Compliance Agent",
        "Test Evaluation Strategy Agent",
        "Application Implementation Validation Agent",
    ]
    if source_type in diagram_source_types:
        owner_agents.insert(2, "Architecture Design Agent")
    if source_type == "learning-plan":
        owner_agents = [
            "Azure AI Learning Orchestrator",
            "Application Planning Companion Agent",
            "Application Implementation Validation Agent",
        ]

    steps = [
        {
            "id": "plan",
            "ownerAgent": owner_agents[0],
            "action": f"Convert the submitted {source_label} into scoped work packages and agent handoffs.",
            "evidence": "Trace each generated step to submitted source text or bundled Agent Foundry documentation.",
        },
        {
            "id": "contract",
            "ownerAgent": owner_agents[min(2, len(owner_agents) - 1)],
            "action": "Define configuration, environment, data, API, and approval boundaries before implementation.",
            "evidence": "Record required settings, missing decisions, validation gates, and blocked assumptions.",
        },
        {
            "id": "validate",
            "ownerAgent": owner_agents[-1],
            "action": "Execute only approved bounded implementation or validation steps in the target workspace.",
            "evidence": "Capture edited files, focused validation command, status, logs, and remaining risks.",
        },
    ]
    if source_type in diagram_source_types:
        steps.insert(
            1,
            {
                "id": "diagram-extract",
                "ownerAgent": "Architecture Design Agent",
                "action": "Extract components, connectors, boundaries, data flows, dependencies, and unclear diagram assumptions before implementation planning.",
                "evidence": "Record diagram format, extracted nodes/connectors, source snippets, and any parts that need human clarification.",
            },
        )

    return {
        "title": title or "Agent Foundry portal run",
        "sourceType": source_type,
        "sourceLabel": source_label,
        "summary": f"Create an approved Agent Foundry execution package from {source_label} input.",
        "goals": goals,
        "ownerAgents": owner_agents,
        "steps": steps,
        "approvalRequired": True,
        "executionMode": "approval-gated-handoff",
        "handoffPrompts": {
            "planning": f"Application Planning Companion Agent, review this portal-created {source_label} plan one step at a time. Do not execute commands. Confirm assumptions, source evidence, owners, and approval gates before handing off.",
            "implementation": "Application Implementation Validation Agent, execute only the approved current step, edit only named files, run focused validation, and summarize evidence plus remaining issues.",
        },
        "guardrails": [
            "Do not claim hosted execution of .agent.md files; they are VS Code/Copilot customization files.",
            "Require human approval before implementation or validation work begins.",
            "Cite source input, bundled docs, file paths, commands, and validation output as evidence.",
            "Block or mark unknown any requirement that cannot be traced to source material.",
        ],
    }


def _build_agent_foundry_evidence(plan: dict) -> list[dict]:
    steps = plan.get("steps") if isinstance(plan, dict) else []
    evidence = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        evidence.append(
            {
                "stepId": step.get("id"),
                "ownerAgent": step.get("ownerAgent"),
                "status": "approved_for_handoff",
                "requiredEvidence": step.get("evidence"),
            }
        )
    evidence.append(
        {
            "stepId": "portal-approval",
            "ownerAgent": "Azure Architecture Factory Portal",
            "status": "recorded",
            "requiredEvidence": "Approval timestamp and approver are stored on the run record.",
        }
    )
    return evidence


def _safe_agent_foundry_run(run: dict, include_plan: bool = True) -> dict:
    agent_payload = run.get("agentFoundry") if isinstance(run.get("agentFoundry"), dict) else {}
    result = run.get("result") if isinstance(run.get("result"), dict) else None
    safe = {
        "id": run.get("id"),
        "kind": "agent-foundry",
        "status": run.get("status"),
        "createdAt": run.get("createdAt"),
        "startedAt": run.get("startedAt"),
        "finishedAt": run.get("finishedAt"),
        "returnCode": run.get("returnCode"),
        "title": agent_payload.get("title"),
        "sourceType": agent_payload.get("sourceType"),
        "diagramFileName": agent_payload.get("diagramFileName"),
        "contentPreview": agent_payload.get("contentPreview"),
        "approvedAt": agent_payload.get("approvedAt"),
        "approvedBy": agent_payload.get("approvedBy"),
        "evidence": agent_payload.get("evidence") or [],
        "result": result,
    }
    if include_plan:
        safe["plan"] = agent_payload.get("plan")
    return safe


# ── Bounded pipeline worker pool ──────────────────────────────────────────────
# Every BRD submission used to spawn a raw daemon thread, which meant 50
# concurrent submissions spawned 50 threads competing for CPU. A bounded pool
# queues extra submissions instead of saturating the container.
_PIPELINE_MAX_WORKERS = int(os.environ.get("AAFACTORY_PIPELINE_MAX_WORKERS", "4"))
_PIPELINE_POOL = ThreadPoolExecutor(
    max_workers=_PIPELINE_MAX_WORKERS,
    thread_name_prefix="aaf-pipeline",
)

# ── Stuck-run watchdog ────────────────────────────────────────────────────────
# A pipeline run whose worker thread dies (segfault, OOM, process SIGKILL)
# leaves its RUNS entry in "running" forever because only the happy path
# transitions the status. The watchdog scans periodically and marks any run
# whose startedAt is older than the threshold as "failed" with a clear
# stderr marker, so the UI surfaces it instead of spinning forever.
_PIPELINE_STUCK_MINUTES = int(os.environ.get("AAFACTORY_PIPELINE_STUCK_MINUTES", "30"))
_PIPELINE_WATCHDOG_INTERVAL_SECONDS = int(
    os.environ.get("AAFACTORY_PIPELINE_WATCHDOG_INTERVAL_SECONDS", "60")
)
_PIPELINE_WATCHDOG_STARTED = False
_PIPELINE_WATCHDOG_LOCK = threading.Lock()


def _parse_iso_z(stamp: str) -> datetime | None:
    """Parse our _utcnow_iso() output back into a tz-aware UTC datetime."""
    if not isinstance(stamp, str) or not stamp.endswith("Z"):
        return None
    try:
        return datetime.fromisoformat(stamp[:-1]).replace(tzinfo=UTC)
    except Exception:
        return None


def _sweep_stuck_runs(now_utc: datetime | None = None) -> int:
    """Mark runs stuck in queued/running past the threshold as failed.

    Returns the number of runs transitioned. Called by the watchdog thread
    and directly by unit tests.
    """
    now_utc = now_utc or datetime.now(UTC)
    threshold = now_utc - timedelta(minutes=_PIPELINE_STUCK_MINUTES)
    transitioned = 0
    with RUNS_LOCK:
        for run_id, run in RUNS.items():
            if not isinstance(run, dict):
                continue
            if run.get("status") not in {"queued", "running"}:
                continue
            anchor_raw = run.get("startedAt") or run.get("createdAt")
            anchor = _parse_iso_z(anchor_raw) if anchor_raw else None
            if anchor is None or anchor >= threshold:
                continue
            logger.warning(
                "Stuck run detected: %s status=%s anchor=%s minutes=%d",
                run_id, run.get("status"), anchor_raw, _PIPELINE_STUCK_MINUTES,
            )
            run["status"] = "failed"
            run["finishedAt"] = _utcnow_iso()
            run["returnCode"] = -2
            run["stderr"] = (
                (run.get("stderr") or "")
                + f"\n[watchdog] Run exceeded {_PIPELINE_STUCK_MINUTES} minutes "
                  "without completion — marked failed."
            )
            if not isinstance(run.get("result"), dict):
                run["result"] = {}
            run["result"].setdefault(
                "message",
                f"Run exceeded {_PIPELINE_STUCK_MINUTES}-minute watchdog threshold.",
            )
            run["result"].setdefault("status", "failed")
            transitioned += 1
        if transitioned:
            _persist_runs_unlocked()
    return transitioned


def _watchdog_loop() -> None:
    while True:
        try:
            time.sleep(_PIPELINE_WATCHDOG_INTERVAL_SECONDS)
            n = _sweep_stuck_runs()
            if n:
                logger.info("Watchdog transitioned %d stuck run(s) to failed", n)
        except Exception as exc:  # noqa: BLE001 - must never die
            logger.warning("Watchdog iteration failed: %s", exc)


def _start_watchdog() -> None:
    """Start the stuck-run watchdog thread once per process."""
    global _PIPELINE_WATCHDOG_STARTED
    with _PIPELINE_WATCHDOG_LOCK:
        if _PIPELINE_WATCHDOG_STARTED:
            return
        _PIPELINE_WATCHDOG_STARTED = True
    t = threading.Thread(
        target=_watchdog_loop, name="aaf-watchdog", daemon=True
    )
    t.start()
    logger.info(
        "Pipeline watchdog started (interval=%ds, stuck-threshold=%dm)",
        _PIPELINE_WATCHDOG_INTERVAL_SECONDS, _PIPELINE_STUCK_MINUTES,
    )

# ── Issued-token store (in-memory, usage-counted) ─────────────────────────────
# Structure: { jti: { "uses": int, "max_uses": int, "exp": float, "sub": str, "purpose": str } }
# Note: resets on server restart — intended for short-lived tokens only.
_ISSUED_TOKENS: dict = {}
_ISSUED_TOKENS_LOCK = threading.Lock()

# ── Token request queue (in-memory) ─────────────────────────────────────
# Structure: [ { "id": str, "sub": str, "reason": str, "requested_at": float, "status": str } ]
_TOKEN_REQUESTS: list = []
_TOKEN_REQUESTS_LOCK = threading.Lock()

# Logging
class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Fields: ts (ISO-8601 UTC), level, logger, msg. Any attributes added via
    `logger.info("...", extra={...})` are merged as top-level keys, so calls
    like `logger.info("run started", extra={"run_id": rid, "owner": upn})`
    produce `{"ts": ..., "msg": "run started", "run_id": ..., "owner": ...}`.
    Exceptions are rendered as a single-string `exc` field.
    """

    # Attributes stdlib LogRecord sets itself; anything outside this set is
    # considered an `extra` key contributed by the caller.
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
                .replace(tzinfo=None).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            # Best-effort serialization; fall back to repr.
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    level_name = os.environ.get("AAFACTORY_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Auto-enable JSON in container environments (ACA sets CONTAINER_APP_NAME)
    # unless explicitly overridden.
    json_env = os.environ.get("AAFACTORY_LOG_JSON", "").strip().lower()
    if json_env in ("1", "true", "yes"):
        use_json = True
    elif json_env in ("0", "false", "no"):
        use_json = False
    else:
        use_json = bool(os.environ.get("CONTAINER_APP_NAME", "").strip())

    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
        )
    root = logging.getLogger()
    # Clear prior handlers so repeated calls (tests) don't stack output.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)


_configure_logging()
logger = logging.getLogger(__name__)


def _runtime_auto_gate_violation(
    generation_options: dict | None,
    output: dict | None,
) -> str | None:
    """Return a blocking reason when runtime:auto is not eligible.

    Enforcement is explicit: only block when caller requested runtime:auto.
    """

    opts = generation_options or {}
    requested_runtime = str(
        opts.get("runtime") or opts.get("orchestratorRuntime") or ""
    ).strip().lower()
    if requested_runtime != "auto":
        return None

    payload = output or {}
    gate = payload.get("orchestratorAutoFlow")
    if not isinstance(gate, dict):
        project_payload = payload.get("project") or {}
        if isinstance(project_payload, dict):
            gate = project_payload.get("orchestratorAutoFlow")

    if not isinstance(gate, dict):
        return None

    if bool(gate.get("eligible")):
        return None

    reason = str(gate.get("reason") or "").strip()
    if reason:
        return f"runtime:auto blocked by BRD readiness gate: {reason}"
    return "runtime:auto blocked by BRD readiness gate."


# ── Azure OpenAI auth header ────────────────────────────────────────────────
# Supports two auth modes:
#   1. API key  (AZURE_OPENAI_API_KEY env var)
#   2. Entra ID (DefaultAzureCredential) — used when azure-identity is importable
#      AND no API key is set. This is how we reach Cognitive Services accounts
#      that have `disableLocalAuth=true`.
# Returns (header_name, header_value) or None when neither auth method works.

_entra_token_cache: dict = {"token": None, "expires_at": 0.0}
_entra_token_lock = threading.Lock()


def _aoai_auth_header() -> tuple[str, str] | None:
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    if api_key:
        return ("api-key", api_key)

    # Fall back to Entra ID via DefaultAzureCredential.
    try:
        from azure.identity import DefaultAzureCredential  # type: ignore
    except ImportError:
        return None

    now = time.time()
    with _entra_token_lock:
        if (_entra_token_cache["token"]
                and _entra_token_cache["expires_at"] - 60 > now):
            return ("Authorization", f"Bearer {_entra_token_cache['token']}")
        try:
            cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
            tok = cred.get_token("https://cognitiveservices.azure.com/.default")
            _entra_token_cache["token"] = tok.token
            _entra_token_cache["expires_at"] = float(tok.expires_on)
            return ("Authorization", f"Bearer {tok.token}")
        except Exception as e:
            logger.warning("Entra token for AOAI failed: %s", e)
            return None


def _aoai_urlopen(req: Request, *, timeout: int = 60) -> bytes:
    """POST to Azure OpenAI with a single retry on transient disconnects.

    AOAI occasionally closes an idle HTTPS keep-alive between requests,
    which surfaces to stdlib urllib as ``RemoteDisconnected`` or
    ``ConnectionResetError``. A single immediate retry fixes it.
    """
    import http.client
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (http.client.RemoteDisconnected,
                http.client.IncompleteRead,
                ConnectionResetError) as e:
            last_exc = e
            logger.warning("AOAI transient disconnect (attempt %d): %s",
                           attempt + 1, e)
            continue
    # Both attempts failed — re-raise the last error.
    raise last_exc  # type: ignore[misc]


def _sanitize_brd_filename(raw_name: str) -> str:
    """Return a safe BRD filename constrained to a simple .md basename."""
    name = pathlib.Path((raw_name or "brd.md").strip()).name
    if not name:
        raise ValueError("Filename is empty")
    if not name.lower().endswith(".md"):
        name = f"{name}.md"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise ValueError("Filename contains invalid characters")
    return name


def _coerce_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


_VALID_NETWORK_TIERS = frozenset({"public", "vnet-integrated", "private"})
_VALID_DEPLOYMENT_MODES = frozenset({"standard", "aca-express"})
_VALID_ACA_EXPRESS_REGIONS = frozenset({"westcentralus", "eastasia"})

_IMPLEMENTATION_LANGUAGE_ALIASES = {
    "python": "python",
    "py": "python",
    "dotnet": "dotnet",
    "net": "dotnet",
    ".net": "dotnet",
    "csharp": "dotnet",
    "c#": "dotnet",
    "aspnet": "dotnet",
    "aspnetcore": "dotnet",
}

_SOURCE_TYPE_ALIASES = {
    "auto": "auto",
    "detect": "auto",
    "infer": "auto",
    "": "brd-markdown",
    "brd": "brd-markdown",
    "brd-markdown": "brd-markdown",
    "requirements": "brd-markdown",
    "architecture-markdown": "architecture-markdown",
    "markdown": "architecture-markdown",
    "md": "architecture-markdown",
    "plain-text": "plain-text",
    "text": "plain-text",
    "txt": "plain-text",
    "drawio": "drawio",
    "draw.io": "drawio",
    "mermaid": "mermaid",
    "mmd": "mermaid",
    "plantuml": "plantuml",
    "puml": "plantuml",
    "structurizr": "structurizr",
    "structurizr-dsl": "structurizr",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "visio": "visio",
    "vsdx": "visio",
    "lucidchart": "lucidchart",
}

_TEXTUAL_SOURCE_TYPES = frozenset(
    {
        "brd-markdown",
        "architecture-markdown",
        "plain-text",
        "drawio",
        "mermaid",
        "plantuml",
        "structurizr",
        "json",
        "yaml",
    }
)

_REFERENCE_ONLY_SOURCE_TYPES = frozenset({"visio", "lucidchart"})

_SOURCE_TYPE_FENCE_LANGUAGES = {
    "architecture-markdown": "markdown",
    "plain-text": "text",
    "drawio": "xml",
    "mermaid": "mermaid",
    "plantuml": "plantuml",
    "structurizr": "text",
    "json": "json",
    "yaml": "yaml",
    "visio": "text",
    "lucidchart": "text",
}


def _sanitize_network_tier(value) -> str:
    """Return a validated network tier string, defaulting to 'public'."""
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _VALID_NETWORK_TIERS else "public"


def _sanitize_deployment_mode(value) -> str:
    """Return a validated deployment mode string, defaulting to 'standard'."""
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _VALID_DEPLOYMENT_MODES else "standard"


def _sanitize_aca_express_region(value) -> str:
    """Return a validated ACA Express region, defaulting to 'westcentralus'."""
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _VALID_ACA_EXPRESS_REGIONS else "westcentralus"


def _sanitize_implementation_language(value) -> str | None:
    """Return canonical implementation language or None when unsupported."""
    candidate = str(value or "").strip().lower().lstrip(".")
    return _IMPLEMENTATION_LANGUAGE_ALIASES.get(candidate)


def _sanitize_source_type(value) -> str:
    """Return canonical architecture source type."""
    candidate = str(value or "").strip().lower()
    return _SOURCE_TYPE_ALIASES.get(candidate, "brd-markdown")


def _looks_like_json(content: str) -> bool:
    sample = (content or "").strip()
    if not sample or sample[0] not in "[{":
        return False
    try:
        json.loads(sample)
        return True
    except Exception:
        return False


def _looks_like_yaml(content: str) -> bool:
    sample = (content or "").strip()
    if not sample or sample.startswith(("#", "```", "<", "{", "[", "@startuml")):
        return False
    lines = [line for line in sample.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    key_value_lines = 0
    for line in lines[:12]:
        stripped = line.strip()
        if stripped.startswith("- "):
            key_value_lines += 1
            continue
        if re.match(r"^[A-Za-z0-9_.-]+\s*:\s*.+$", stripped):
            key_value_lines += 1
    return key_value_lines >= 2


def _detect_source_type(
    *,
    file_name: str = "",
    content: str = "",
    uploaded_file_name: str = "",
    raw_bytes: bytes | None = None,
) -> str:
    """Infer the architecture intake format from filename and content."""
    sample_name = (uploaded_file_name or file_name or "").strip().lower()
    suffix = pathlib.Path(sample_name).suffix.lower()
    normalized = (content or "").strip()

    if suffix == ".drawio":
        return "drawio"
    if suffix in {".mmd", ".mermaid"}:
        return "mermaid"
    if suffix in {".puml", ".plantuml"}:
        return "plantuml"
    if suffix == ".dsl":
        return "structurizr"
    if suffix == ".json":
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix in {".vsdx", ".vsd"}:
        return "visio"
    if "lucidchart" in sample_name or suffix == ".lucid":
        return "lucidchart"

    lowered = normalized.lower()
    if "<mxgraphmodel" in lowered or "<mxfile" in lowered:
        return "drawio"
    if re.search(r"(?m)^\s*@startuml\b", normalized):
        return "plantuml"
    if re.search(r"(?m)^\s*(graph|flowchart|sequencediagram|classdiagram|statediagram|erdiagram|journey|gantt|mindmap|timeline|architecture-beta)\b", lowered):
        return "mermaid"
    if re.search(r"(?m)^\s*workspace\s*\{", lowered) or ("views {" in lowered and "model {" in lowered):
        return "structurizr"
    if _looks_like_json(normalized):
        return "json"
    if _looks_like_yaml(normalized):
        return "yaml"
    if re.search(r"(?m)^\s*#\s+", normalized):
        if re.search(r"business goal|key requirements|success criteria|out of scope|timeline", lowered):
            return "brd-markdown"
        return "architecture-markdown"

    if raw_bytes is not None:
        if raw_bytes.startswith(b"PK") and suffix == ".vsdx":
            return "visio"
        if raw_bytes.startswith(b"%PDF") and "lucid" in sample_name:
            return "lucidchart"

    return "plain-text"


def _normalize_node_label(raw: str) -> str:
    label = html.unescape(str(raw or ""))
    label = re.sub(r"<[^>]+>", " ", label)
    label = re.sub(r"\s+", " ", label).strip()
    return label[:120]


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = value.strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _extract_mermaid_summary(content: str) -> tuple[list[str], list[str], list[str]]:
    nodes: list[str] = []
    relationships: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        node_matches = re.findall(r"\b([A-Za-z0-9_]+)\s*\[(.*?)\]", stripped)
        for alias, label in node_matches:
            nodes.append(_normalize_node_label(label or alias))
        edge_match = re.search(
            r"^\s*([A-Za-z0-9_]+)(?:\[(.*?)\])?\s*[-.=]+(?:>|\|[^|]*\|>)\s*([A-Za-z0-9_]+)(?:\[(.*?)\])?(?:\s*\|([^|]+)\|)?",
            stripped,
        )
        if edge_match:
            src, src_label, dst, dst_label, edge_label = edge_match.groups()
            nodes.append(_normalize_node_label(src_label or src))
            nodes.append(_normalize_node_label(dst_label or dst))
            relation = f"{src} -> {dst}"
            edge_label = edge_label or ""
            if edge_label.strip():
                relation += f" ({_normalize_node_label(edge_label)})"
            relationships.append(relation)
    signals = ["Mermaid graph parsed"] if relationships else []
    return _dedupe_preserve(nodes), _dedupe_preserve(relationships), signals


def _extract_plantuml_summary(content: str) -> tuple[list[str], list[str], list[str]]:
    nodes: list[str] = []
    relationships: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("'") or stripped.startswith("@"):
            continue
        relation_match = re.search(r"([\w.:-]+)\s*[-=.]+(?:left|right|up|down)?[-=.]*>\s*([\w.:-]+)\s*:?[ ]*(.*)", stripped)
        if relation_match:
            src, dst, label = relation_match.groups()
            relation = f"{src} -> {dst}"
            if label.strip():
                relation += f" ({_normalize_node_label(label)})"
            relationships.append(relation)
            nodes.extend([src, dst])
            continue
        decl_match = re.search(r"^(actor|participant|component|database|queue|rectangle|node|cloud)\s+\"?([^\"]+)\"?", stripped, re.IGNORECASE)
        if decl_match:
            nodes.append(_normalize_node_label(decl_match.group(2)))
    signals = ["PlantUML diagram parsed"] if relationships else []
    return _dedupe_preserve(nodes), _dedupe_preserve(relationships), signals


def _extract_structurizr_summary(content: str) -> tuple[list[str], list[str], list[str]]:
    nodes: list[str] = []
    relationships: list[str] = []
    alias_map: dict[str, str] = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        decl_match = re.match(r"([A-Za-z0-9_]+)\s*=\s*(softwareSystem|container|person|deploymentNode|component)\s+\"([^\"]+)\"", stripped, re.IGNORECASE)
        if decl_match:
            alias, kind, label = decl_match.groups()
            normalized = _normalize_node_label(label)
            alias_map[alias] = normalized
            nodes.append(f"{normalized} [{kind}]")
            continue
        relation_match = re.match(r"([A-Za-z0-9_]+)\s*->\s*([A-Za-z0-9_]+)\s+\"([^\"]+)\"", stripped)
        if relation_match:
            src, dst, label = relation_match.groups()
            relationships.append(
                f"{alias_map.get(src, src)} -> {alias_map.get(dst, dst)} ({_normalize_node_label(label)})"
            )
    signals = ["Structurizr DSL parsed"] if alias_map else []
    return _dedupe_preserve(nodes), _dedupe_preserve(relationships), signals


def _extract_drawio_summary(content: str) -> tuple[list[str], list[str], list[str]]:
    """Extract components and relationships from a draw.io XML diagram.

    Uses stdlib ElementTree for proper XML parsing and extracts node labels from
    ``value``/``label`` attributes plus edge ``source``/``target`` connections.
    Falls back to regex-based label scan when XML is malformed.
    """
    nodes: list[str] = []
    relationships: list[str] = []
    signals: list[str] = []

    # draw.io XML may be wrapped in <mxGraphModel> or <mxfile>; try parsing
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        # Malformed XML: fall back to simple regex label scan
        labels = _dedupe_preserve(
            [
                _normalize_node_label(m)
                for m in re.findall(r'(?:value|label)="([^"]+)"', content, flags=re.IGNORECASE)
                if _normalize_node_label(m)
            ]
        )
        return labels[:20], [], ["draw.io labels extracted (regex fallback)"]

    # Build a mapping from cell id -> human-readable label for relationship rendering
    id_to_label: dict[str, str] = {}
    vertex_cells: list[ET.Element] = []
    edge_cells: list[ET.Element] = []

    for cell in root.iter("mxCell"):
        cell_id = cell.get("id", "")
        raw_label = cell.get("value") or cell.get("label") or ""
        label = _normalize_node_label(raw_label)

        is_vertex = cell.get("vertex") == "1"
        is_edge = cell.get("edge") == "1"
        has_source = bool(cell.get("source"))
        has_target = bool(cell.get("target"))

        if is_vertex and label:
            id_to_label[cell_id] = label
            vertex_cells.append(cell)
        elif is_edge or has_source or has_target:
            edge_cells.append(cell)

    # Collect node labels (deduplicated)
    nodes = _dedupe_preserve([id_to_label[c.get("id", "")] for c in vertex_cells if id_to_label.get(c.get("id", ""))])

    # Build relationships from edge source->target
    for cell in edge_cells:
        src_id = cell.get("source", "")
        dst_id = cell.get("target", "")
        src = id_to_label.get(src_id, src_id or "?")
        dst = id_to_label.get(dst_id, dst_id or "?")
        if src and dst and src != "?" and dst != "?":
            edge_label = _normalize_node_label(cell.get("value") or cell.get("label") or "")
            rel = f"{src} -> {dst}"
            if edge_label:
                rel += f" ({edge_label})"
            relationships.append(rel)

    signals.append("draw.io XML parsed")
    if relationships:
        signals.append(f"{len(relationships)} edge(s) extracted")
    return nodes[:25], _dedupe_preserve(relationships)[:20], signals


def _extract_json_summary(content: str) -> tuple[list[str], list[str], list[str]]:
    try:
        payload = json.loads(content)
    except Exception:
        return [], [], []
    nodes: list[str] = []
    relationships: list[str] = []
    signals: list[str] = []
    if isinstance(payload, dict):
        signals.append("JSON architecture spec parsed")
        for key in ("services", "components", "systems", "containers"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value[:12]:
                    if isinstance(item, dict):
                        nodes.append(_normalize_node_label(item.get("name") or item.get("id") or item.get("title") or key))
                    else:
                        nodes.append(_normalize_node_label(str(item)))
        rels = payload.get("relationships") or payload.get("flows")
        if isinstance(rels, list):
            for item in rels[:12]:
                if isinstance(item, dict):
                    src = _normalize_node_label(item.get("source") or item.get("from") or "source")
                    dst = _normalize_node_label(item.get("target") or item.get("to") or "target")
                    label = _normalize_node_label(item.get("label") or item.get("description") or "")
                    relationships.append(f"{src} -> {dst}" + (f" ({label})" if label else ""))
    return _dedupe_preserve(nodes), _dedupe_preserve(relationships), signals


def _extract_yaml_summary(content: str) -> tuple[list[str], list[str], list[str]]:
    nodes: list[str] = []
    relationships: list[str] = []
    current_section = ""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        section_match = re.match(r"^([A-Za-z0-9_.-]+):\s*$", stripped)
        if section_match:
            current_section = section_match.group(1)
            continue
        list_name_match = re.match(r"^-\s+([A-Za-z0-9_.-]+)$", stripped)
        if current_section in {"services", "components", "systems", "containers"} and list_name_match:
            nodes.append(_normalize_node_label(list_name_match.group(1)))
            continue
        relation_match = re.match(r"^(source|from):\s*(.+)$", stripped)
        if relation_match:
            relationships.append(_normalize_node_label(stripped))
    signals = ["YAML architecture spec parsed"] if nodes or relationships else []
    return _dedupe_preserve(nodes), _dedupe_preserve(relationships), signals


def _summarize_architecture_source(source_type: str, content: str) -> dict[str, list[str]]:
    normalized = (content or "").strip()
    summary = {"components": [], "relationships": [], "signals": []}
    if not normalized:
        return summary

    if source_type == "mermaid":
        components, relationships, signals = _extract_mermaid_summary(normalized)
    elif source_type == "plantuml":
        components, relationships, signals = _extract_plantuml_summary(normalized)
    elif source_type == "structurizr":
        components, relationships, signals = _extract_structurizr_summary(normalized)
    elif source_type == "drawio":
        components, relationships, signals = _extract_drawio_summary(normalized)
    elif source_type == "json":
        components, relationships, signals = _extract_json_summary(normalized)
    elif source_type == "yaml":
        components, relationships, signals = _extract_yaml_summary(normalized)
    elif source_type in {"architecture-markdown", "plain-text", "brd-markdown"}:
        bullet_items = [re.sub(r"^[-*]\s+", "", line.strip()) for line in normalized.splitlines() if re.match(r"^\s*[-*]\s+", line)]
        components, relationships, signals = _dedupe_preserve(bullet_items[:12]), [], []
    else:
        components, relationships, signals = [], [], []

    summary["components"] = components[:12]
    summary["relationships"] = relationships[:12]
    summary["signals"] = signals[:6]
    return summary


def _sanitize_project_slug(value) -> str | None:
    """Return a safe project slug or None when absent or invalid."""
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", candidate):
        return None
    return candidate


# ── Repo Intake helpers ───────────────────────────────────────────────────────

# Allowed git hosts for repo intake (HTTPS only)
_ALLOWED_REPO_HOSTS: frozenset[str] = frozenset({
    "github.com",
    "dev.azure.com",
})

# Limits
_MAX_REPO_BRANCH_SUFFIX_LEN = 50
_MAX_REPO_AUTOMATION_GOAL_CHARS = 4000
_MAX_REPO_FILE_READ_BYTES = 65_536     # max bytes read per file during analysis
_REPO_CLONE_TIMEOUT_SECONDS = 120      # git clone hard timeout
_AAF_ANALYSIS_REPORT_FILE = "AAF-analysis-report.md"
_AAF_CHANGE_SUMMARY_FILE = "AAF-change-summary.md"
_AAF_REPO_CHANGE_AGENT = "repo-change-agent"
_REPO_WORKFLOW_MODES: frozenset[str] = frozenset({
    "analysis-only",
    "implement-pr",
})

# Extensions to include in the code inventory
_CODE_EXTENSIONS: dict[str, str] = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript/React",
    ".js": "JavaScript", ".jsx": "JavaScript/React",
    ".cs": "C#", ".java": "Java", ".go": "Go", ".rs": "Rust",
    ".rb": "Ruby", ".php": "PHP", ".kt": "Kotlin", ".swift": "Swift",
    ".cpp": "C++", ".c": "C",
    ".bicep": "Bicep", ".tf": "Terraform",
    ".yaml": "YAML", ".yml": "YAML", ".json": "JSON", ".md": "Markdown",
}

# Filename keywords that indicate an architecture file
_ARCH_KEYWORDS: frozenset[str] = frozenset({
    "architecture", "arch", "diagram", "design", "drawio",
    "mermaid", "plantuml", "structurizr", "system", "infrastructure", "infra",
})

# Tech-stack manifest filenames / globs to detect
_MANIFEST_GLOBS: list[str] = [
    "package.json", "pom.xml", "build.gradle", "build.gradle.kts",
    "requirements.txt", "setup.py", "pyproject.toml",
    "*.csproj", "*.fsproj",
    "Cargo.toml", "go.mod", "Gemfile",
]


def _validate_repo_url(raw_url: str) -> tuple[str, str | None]:
    """Validate and normalise an HTTPS repository URL.

    Returns ``(normalised_url, None)`` on success or ``("", error_msg)``.
    Only HTTPS URLs on known hosts are accepted; embedded credentials are
    stripped from the returned URL.
    """
    raw = raw_url.strip()
    if not raw:
        return "", "repoUrl is required"
    try:
        parsed = urlparse(raw)
    except Exception:
        return "", "repoUrl could not be parsed"
    if parsed.scheme != "https":
        return "", "repoUrl must use https://"
    hostname = (parsed.hostname or "").lower()
    if hostname not in _ALLOWED_REPO_HOSTS:
        allowed = ", ".join(sorted(_ALLOWED_REPO_HOSTS))
        return "", f"repoUrl host '{hostname}' is not supported; allowed: {allowed}"
    # Return a credential-free URL for storage / display
    port_part = f":{parsed.port}" if parsed.port else ""
    safe_netloc = hostname + port_part
    safe_url = parsed._replace(netloc=safe_netloc).geturl()
    return safe_url, None


def _validate_local_repo_path(raw_path: str) -> tuple[pathlib.Path | None, str | None]:
    """Validate and resolve a local repository path for intake."""
    candidate = str(raw_path or "").strip()
    if not candidate:
        return None, "localRepoPath is required when inputSource is local"
    try:
        resolved = pathlib.Path(candidate).expanduser().resolve()
    except Exception:
        return None, "localRepoPath could not be resolved"
    if not resolved.exists() or not resolved.is_dir():
        return None, "localRepoPath must point to an existing directory"
    if not (resolved / ".git").exists():
        return None, "localRepoPath must point to a git repository (missing .git)"
    return resolved, None


def _sanitize_branch_suffix(raw: str) -> tuple[str, str | None]:
    """Return a validated branch-name suffix or an error string."""
    candidate = raw.strip()
    if not candidate:
        return "", "branchSuffix is required"
    if len(candidate) > _MAX_REPO_BRANCH_SUFFIX_LEN:
        return "", f"branchSuffix must be at most {_MAX_REPO_BRANCH_SUFFIX_LEN} characters"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", candidate):
        return "", (
            "branchSuffix must start with a letter or digit and contain only "
            "letters, digits, hyphens, underscores, or dots"
        )
    return candidate, None


def _sanitize_repo_workflow_mode(raw: object) -> tuple[str, str | None]:
    """Validate repo intake workflow mode."""
    candidate = str(raw or "").strip().lower() or "analysis-only"
    if candidate not in _REPO_WORKFLOW_MODES:
        allowed = ", ".join(sorted(_REPO_WORKFLOW_MODES))
        return "", f"workflowMode must be one of: {allowed}"
    return candidate, None


def _sanitize_repo_automation_goal(raw: object) -> tuple[str, str | None]:
    """Validate an optional freeform automation goal."""
    if raw in (None, ""):
        return "", None
    goal = str(raw).strip()
    if len(goal) > _MAX_REPO_AUTOMATION_GOAL_CHARS:
        return "", (
            f"automationGoal must be at most {_MAX_REPO_AUTOMATION_GOAL_CHARS} characters"
        )
    return goal, None


def _make_authed_clone_url(repo_url: str, pat: str) -> str:
    """Return a clone URL with PAT credentials embedded.  Never log the result."""
    parsed = urlparse(repo_url)
    hostname = (parsed.hostname or "").lower()
    port_part = f":{parsed.port}" if parsed.port else ""
    if hostname == "dev.azure.com":
        # Azure DevOps: any username + PAT works; use 'pat' as username
        authed_netloc = f"pat:{pat}@{hostname}{port_part}"
    else:
        # GitHub: PAT as bearer token
        authed_netloc = f"x-oauth-basic:{pat}@{hostname}{port_part}"
    return parsed._replace(netloc=authed_netloc).geturl()


def _git_run(
    args: list[str],
    cwd: str | None = None,
    *,
    timeout: int = 60,
) -> tuple[str, str, int]:
    """Run a git sub-command and return (stdout, stderr, returncode).

    Credentials must NOT appear in *args* — embed them in the remote URL.
    """
    cmd = ["git", *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired:
        return "", f"git {args[0]} timed out after {timeout}s", -1
    except FileNotFoundError:
        return "", "git executable not found on PATH", -1
    return result.stdout or "", result.stderr or "", result.returncode


def _mask_pat_in_text(text: str) -> str:
    """Replace any embedded PAT-looking credentials in a string before logging."""
    return re.sub(r"https?://[^@\s]{1,200}@", "https://***@", text)


def _clone_repo(clone_url: str, target_dir: str) -> tuple[bool, str]:
    """Shallow-clone *clone_url* into *target_dir*.

    Returns ``(success, error_msg)``.
    """
    _, stderr, rc = _git_run(
        ["clone", "--depth", "1", clone_url, target_dir],
        timeout=_REPO_CLONE_TIMEOUT_SECONDS,
    )
    if rc != 0:
        return False, f"git clone failed (rc={rc}): {_mask_pat_in_text(stderr).strip()[:400]}"
    return True, ""


def _clone_local_repo(source_dir: str, target_dir: str) -> tuple[bool, str]:
    """Clone a local repository into *target_dir* preserving git metadata."""
    _, stderr, rc = _git_run(
        ["clone", source_dir, target_dir],
        timeout=_REPO_CLONE_TIMEOUT_SECONDS,
    )
    if rc != 0:
        return False, f"local git clone failed (rc={rc}): {stderr.strip()[:400]}"
    return True, ""


def _create_aaf_branch(repo_dir: str, branch_name: str, push_url: str) -> tuple[bool, str]:
    """Create *branch_name* locally and push it.  Returns ``(success, error_msg)``."""
    # Configure a minimal git identity required for commits inside the container
    _git_run(["config", "user.email", "aaf-bot@factory.local"], cwd=repo_dir, timeout=10)
    _git_run(["config", "user.name", "Azure Architecture Factory"], cwd=repo_dir, timeout=10)
    _, stderr, rc = _git_run(["checkout", "-b", branch_name], cwd=repo_dir, timeout=15)
    if rc != 0:
        return False, f"Failed to create branch '{branch_name}': {stderr.strip()[:200]}"
    # Push the empty branch so the remote reference exists before the commit
    _, stderr, rc = _git_run(
        ["push", push_url, f"{branch_name}:{branch_name}"],
        cwd=repo_dir,
        timeout=30,
    )
    if rc != 0:
        return False, f"Failed to push branch: {_mask_pat_in_text(stderr).strip()[:400]}"
    return True, ""


def _detect_default_branch(repo_dir: str) -> tuple[str, str | None]:
    """Determine the remote default branch for a cloned repository."""
    stdout, stderr, rc = _git_run(
        ["symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=repo_dir,
        timeout=15,
    )
    if rc == 0:
        ref = stdout.strip()
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix):
            branch = ref[len(prefix):].strip()
            if branch:
                return branch, None

    stdout, stderr, rc = _git_run(
        ["rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_dir,
        timeout=15,
    )
    if rc == 0:
        branch = stdout.strip()
        if branch and branch != "HEAD":
            return branch, None

    return "main", f"Failed to determine default branch: {stderr.strip()[:200]}"


def _repo_provider(repo_url: str) -> str:
    hostname = (urlparse(repo_url).hostname or "").lower()
    if hostname == "github.com":
        return "github"
    if hostname == "dev.azure.com":
        return "azure-devops"
    return "unknown"


def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("GitHub repo URL must include owner/repo")
    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def _parse_azure_devops_repo(repo_url: str) -> tuple[str, str, str]:
    parsed = urlparse(repo_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 4 or parts[2] != "_git":
        raise ValueError("Azure DevOps repo URL must look like /org/project/_git/repo")
    org = parts[0]
    project = parts[1]
    repo = parts[3]
    return org, project, repo


def _build_remote_file_url(repo_url: str, branch_name: str, file_path: str) -> str | None:
    provider = _repo_provider(repo_url)
    relative_path = file_path.lstrip("/")
    if provider == "github":
        owner, repo = _parse_github_repo(repo_url)
        return f"https://github.com/{owner}/{repo}/blob/{branch_name}/{relative_path}"
    if provider == "azure-devops":
        org, project, repo = _parse_azure_devops_repo(repo_url)
        return (
            f"https://dev.azure.com/{org}/{project}/_git/{repo}"
            f"?path=%2F{relative_path.replace('/', '%2F')}&version=GB{branch_name}"
        )
    return None


def _derive_repo_project_slug(repo_url: str, run_id: str) -> str:
    """Create a stable, safe slug for a repo-intake project snapshot."""
    parsed = urlparse(repo_url)
    parts = [p for p in parsed.path.split("/") if p]
    provider = _repo_provider(repo_url)

    base = "repo"
    if provider == "github" and len(parts) >= 2:
        base = f"{parts[0]}-{parts[1].removesuffix('.git')}"
    elif provider == "azure-devops" and len(parts) >= 4 and parts[2] == "_git":
        base = f"{parts[1]}-{parts[3].removesuffix('.git')}"
    elif parts:
        base = parts[-1].removesuffix(".git") or "repo"

    cleaned_base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "repo"
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    candidate = f"repo-intake-{cleaned_base[:64]}-{timestamp}"
    slug = _sanitize_project_slug(candidate)
    if slug:
        return slug
    return f"repo-intake-{timestamp}-{run_id.replace('-', '')[:8].lower()}"


def _record_project_owner(slug: str, owner: str) -> None:
    """Best-effort owner assignment for Entra project visibility filtering."""
    normalized_owner = (owner or "").strip().lower()
    if not normalized_owner:
        return
    try:
        data = _load_owners()
        projects = data.setdefault("projects", {})
        existing = projects.get(slug) or []
        if isinstance(existing, str):
            existing = [existing]
        lowered = {e.strip().lower() for e in existing if isinstance(e, str)}
        if normalized_owner not in lowered:
            existing.append(normalized_owner)
            projects[slug] = existing
            _save_owners(data)
    except Exception as exc:  # noqa: BLE001 - best-effort
        logger.warning("Failed to persist owner for repo-intake project %s: %s", slug, exc)


def _persist_repo_intake_project(
    repo_dir: pathlib.Path,
    *,
    repo_url: str,
    branch_name: str,
    workflow_mode: str,
    automation_goal: str,
    run_id: str,
    requested_by: str,
    analysis: dict,
) -> tuple[str | None, str | None, str | None]:
    """Persist a completed repo-intake run as a local project card/workspace."""
    try:
        if not repo_dir.exists() or not repo_dir.is_dir():
            return None, None, f"Repo directory does not exist: {repo_dir}"

        parsed = urlparse(repo_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        provider = _repo_provider(repo_url)
        title_repo = parsed.netloc or "repository"
        if provider == "github" and len(path_parts) >= 2:
            title_repo = f"{path_parts[0]}/{path_parts[1].removesuffix('.git')}"
        elif provider == "azure-devops" and len(path_parts) >= 4 and path_parts[2] == "_git":
            title_repo = f"{path_parts[1]}/{path_parts[3].removesuffix('.git')}"
        elif path_parts:
            title_repo = path_parts[-1].removesuffix(".git")
        project_title = f"Imported Repo: {title_repo}"

        projects_root = FACTORY_REPO_ROOT / "projects"
        projects_root.mkdir(parents=True, exist_ok=True)

        base_slug = _derive_repo_project_slug(repo_url, run_id)
        slug = base_slug
        suffix = 2
        while (projects_root / slug).exists():
            tail = f"-{suffix}"
            slug = f"{base_slug[:120 - len(tail)]}{tail}"
            suffix += 1

        project_root = projects_root / slug
        shutil.move(str(repo_dir), str(project_root))

        # Keep imported projects lightweight and avoid exposing raw git internals.
        shutil.rmtree(project_root / ".git", ignore_errors=True)
        shutil.rmtree(project_root / "outputs" / "copilot", ignore_errors=True)

        docs_dir = project_root / "docs"
        intake_dir = docs_dir / "intake"
        docs_dir.mkdir(parents=True, exist_ok=True)
        intake_dir.mkdir(parents=True, exist_ok=True)

        architecture_overview = docs_dir / "architecture-overview.md"
        if not architecture_overview.is_file():
            tech_stack = ", ".join(analysis.get("tech_stack", [])[:8]) or "not detected"
            top_dirs = ", ".join(analysis.get("dir_tree", [])[:12]) or "not detected"
            arch_files = [af.get("name", "") for af in analysis.get("arch_files", []) if af.get("name")]
            arch_text = "\n".join(f"- {name}" for name in arch_files[:10]) or "- none detected"
            architecture_overview.write_text(
                "\n".join([
                    "# Architecture Overview",
                    "",
                    "This project was imported from a repository intake run.",
                    "",
                    f"- Repository: {repo_url}",
                    f"- Branch analyzed: {branch_name}",
                    f"- Workflow mode: {workflow_mode}",
                    "",
                    "## Detected Tech Stack",
                    "",
                    f"{tech_stack}",
                    "",
                    "## Top-Level Structure",
                    "",
                    f"{top_dirs}",
                    "",
                    "## Architecture Artifacts",
                    "",
                    arch_text,
                    "",
                ]),
                encoding="utf-8",
            )

        intake_report = intake_dir / "repo-intake.md"
        intake_report.write_text(
            "\n".join([
                "# Repository Intake Metadata",
                "",
                f"- Run ID: `{run_id}`",
                f"- Repository URL: {repo_url}",
                f"- Branch: `{branch_name}`",
                f"- Workflow mode: `{workflow_mode}`",
                f"- Requested by: `{requested_by or 'unknown'}`",
                f"- Recorded at: `{_utcnow_iso()}`",
                "",
                "## Automation Goal",
                "",
                automation_goal or "No explicit goal was supplied.",
                "",
                f"## Analysis Artifact",
                "",
                f"- `{_AAF_ANALYSIS_REPORT_FILE}`",
                "",
                "## Change Summary Artifact",
                "",
                f"- `{_AAF_CHANGE_SUMMARY_FILE}` (present only for implement-pr)",
                "",
            ]),
            encoding="utf-8",
        )

        links: dict[str, str] = {
            "architectureOverview": f"projects/{slug}/docs/architecture-overview.md",
        }
        readme_path = project_root / "README.md"
        if readme_path.is_file():
            links["readme"] = f"projects/{slug}/README.md"
        if (project_root / _AAF_ANALYSIS_REPORT_FILE).is_file():
            links["analysisReport"] = f"projects/{slug}/{_AAF_ANALYSIS_REPORT_FILE}"
        if (project_root / _AAF_CHANGE_SUMMARY_FILE).is_file():
            links["changeSummary"] = f"projects/{slug}/{_AAF_CHANGE_SUMMARY_FILE}"

        manifest = {
            "title": project_title,
            "status": "Ready",
            "source_brd": repo_url,
            "created_at": _utcnow_iso(),
            "generation_options": {
                "sourceType": "repo-intake",
                "workflowMode": workflow_mode,
                "automationGoal": automation_goal,
            },
            "links": links,
            "repo_intake": {
                "repo_url": repo_url,
                "branch_name": branch_name,
                "workflow_mode": workflow_mode,
                "run_id": run_id,
            },
        }
        (project_root / "project-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        _record_project_owner(slug, requested_by)
        return slug, project_title, None
    except Exception as exc:  # noqa: BLE001
        return None, None, str(exc)


def _build_repo_change_prompt(
    repo_url: str,
    branch_name: str,
    analysis: dict,
    automation_goal: str = "",
) -> str:
    """Build a compact prompt for the dedicated repo-change agent."""
    tech_stack = ", ".join(analysis.get("tech_stack", [])[:8]) or "not detected"
    arch_files = [af.get("name", "") for af in analysis.get("arch_files", [])[:10] if af.get("name")]
    arch_list = ", ".join(arch_files) or "none detected"
    dir_tree = ", ".join(analysis.get("dir_tree", [])[:12]) or "not detected"

    lines = [
        "Operate on the already-cloned target repository using the dedicated repo-change-agent instructions.",
        f"Repository: {repo_url}",
        f"Working branch: {branch_name}",
        "",
        "Context detected before your run:",
        f"- Tech stack manifests: {tech_stack}",
        f"- Architecture artifacts: {arch_list}",
        f"- Top-level structure: {dir_tree}",
        f"- Start by reading `{_AAF_ANALYSIS_REPORT_FILE}` if present.",
        f"- You must leave behind `{_AAF_CHANGE_SUMMARY_FILE}`.",
        "- Do not commit, push, or open a PR.",
    ]
    if automation_goal:
        lines.extend([
            "",
            "Explicit user goal:",
            automation_goal,
        ])
    else:
        lines.extend([
            "",
            "No explicit feature request was provided.",
            "Infer the highest-value architecture-aligned enhancement from the repository's current docs, architecture, source, and infra.",
        ])
    return "\n".join(lines)


def _set_run_progress(
    run_id: str,
    *,
    stage: str,
    message: str = "",
    log_preview: str = "",
) -> None:
    """Persist lightweight progress for long-running repo workflows."""
    with RUNS_LOCK:
        run = RUNS.get(run_id)
        if not run:
            return
        run["progress"] = {
            "stage": stage,
            "message": message,
            "logPreview": log_preview[-6000:] if log_preview else "",
            "updatedAt": _utcnow_iso(),
        }
        if log_preview:
            run["logTail"] = log_preview[-50000:]
        _persist_runs_unlocked()


def _wait_for_repo_copilot_run(
    repo_dir: pathlib.Path,
    copilot_run_id: str,
    portal_run_id: str,
) -> tuple[dict | None, str | None]:
    """Wait for a Copilot CLI run launched inside a cloned repo to finish."""
    timeout = 1860
    if copilot_runner is not None:
        try:
            timeout = int(copilot_runner.runtime_info().get("timeoutSec") or timeout) + 60
        except Exception:
            pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = copilot_runner.get_run(repo_dir, copilot_run_id)
        if run is None:
            return None, "Copilot run metadata disappeared before completion"
        status = run.get("status") or "unknown"
        log_tail = copilot_runner.read_log_tail(repo_dir, copilot_run_id) or ""
        _set_run_progress(
            portal_run_id,
            stage="repo-change-agent",
            message=f"Repo change agent status: {status}",
            log_preview=log_tail,
        )
        if status in {"succeeded", "failed", "timeout", "cancelled", "unknown"}:
            return run, None
        time.sleep(2)
    try:
        copilot_runner.cancel_run(repo_dir, copilot_run_id)
    except Exception:
        pass
    return None, "Copilot run timed out waiting for completion"


def _remove_repo_copilot_artifacts(repo_dir: pathlib.Path, run_id: str) -> None:
    """Remove local Copilot runner artifacts so they are not committed to the target repo."""
    run_path = repo_dir / "outputs" / "copilot" / run_id
    try:
        shutil.rmtree(run_path, ignore_errors=True)
    except Exception:
        pass
    for maybe_empty in [run_path.parent, (repo_dir / "outputs")]:
        try:
            if maybe_empty.is_dir() and not any(maybe_empty.iterdir()):
                maybe_empty.rmdir()
        except Exception:
            pass


def _git_diff_stat(repo_dir: str) -> str:
    """Return a short git diff stat summary for the working tree."""
    stdout, _, rc = _git_run(["diff", "--stat"], cwd=repo_dir, timeout=20)
    if rc != 0:
        return ""
    return stdout.strip()


def _ensure_change_summary(repo_dir: str, automation_goal: str, copilot_run_id: str) -> None:
    """Ensure the implementation workflow leaves behind a change summary artifact."""
    summary_path = pathlib.Path(repo_dir) / _AAF_CHANGE_SUMMARY_FILE
    if summary_path.is_file():
        return
    diff_stat = _git_diff_stat(repo_dir) or "No diff stat available."
    lines = [
        f"# {_AAF_CHANGE_SUMMARY_FILE[:-3].replace('-', ' ').title()}",
        "",
        "This fallback summary was created by the portal because the Copilot run completed",
        "without writing the expected summary artifact.",
        "",
        "## Decision",
        "",
        "Enhancement path completed, but rationale must be reviewed from the changed files.",
        "",
        "## Requested Goal",
        "",
        automation_goal or "No explicit goal was supplied; the run was autonomous.",
        "",
        "## Validation",
        "",
        "Review the repository diff and Copilot run log for exact commands and outcomes.",
        "",
        "## Diff Stat",
        "",
        "```text",
        diff_stat,
        "```",
        "",
        f"Copilot run id: `{copilot_run_id}`",
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def _commit_and_push_all_changes(
    repo_dir: str,
    branch_name: str,
    push_url: str,
    commit_message: str,
) -> tuple[bool, str]:
    """Commit every staged/untracked change and push the branch."""
    _git_run(["add", "-A"], cwd=repo_dir, timeout=20)
    stdout, stderr, rc = _git_run(["status", "--porcelain"], cwd=repo_dir, timeout=20)
    if rc != 0:
        return False, f"git status failed: {stderr.strip()[:300]}"
    if not stdout.strip():
        return False, "No file changes were produced by the AAF workflow"
    _, stderr, rc = _git_run(["commit", "-m", commit_message], cwd=repo_dir, timeout=30)
    if rc != 0:
        return False, f"git commit failed: {stderr.strip()[:300]}"
    _, stderr, rc = _git_run(["push", push_url, f"{branch_name}:{branch_name}"], cwd=repo_dir, timeout=60)
    if rc != 0:
        return False, f"git push failed: {_mask_pat_in_text(stderr).strip()[:400]}"
    return True, ""


def _http_json_request(url: str, *, method: str, headers: dict[str, str], payload: dict) -> tuple[dict | None, str | None]:
    """POST JSON and return parsed JSON or an error string."""
    data = None if method.upper() == "GET" else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}, None
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(exc)
        return None, f"HTTP {exc.code}: {body[:600]}"
    except URLError as exc:
        return None, str(exc)


def _build_repo_pr_title(repo_url: str, automation_goal: str) -> str:
    """Create a concise PR title for AAF-generated repo changes."""
    repo_name = pathlib.Path(urlparse(repo_url).path.rstrip("/")).name.replace(".git", "") or "repo"
    if automation_goal:
        truncated = automation_goal.strip().splitlines()[0][:72].strip()
        return f"AAF: {truncated}"
    return f"AAF: architecture-aligned enhancement for {repo_name}"


def _build_repo_pr_body(branch_name: str, base_branch: str, automation_goal: str) -> str:
    """Build a PR body that points reviewers to the generated artifacts."""
    lines = [
        "## Azure Architecture Factory Automation",
        "",
        f"- Working branch: `{branch_name}`",
        f"- Target branch: `{base_branch}`",
        f"- Analysis artifact: `{_AAF_ANALYSIS_REPORT_FILE}`",
        f"- Change summary artifact: `{_AAF_CHANGE_SUMMARY_FILE}`",
        "",
        "The factory reviewed the repository docs, architecture artifacts, source code, and infrastructure,",
        "then decided whether to enhance existing implementation surfaces or add minimal new code aligned to the repo's current design.",
        "",
        "Validation details and remaining risks are documented in the generated change summary file.",
    ]
    if automation_goal:
        lines.extend([
            "",
            "## Requested Goal",
            "",
            automation_goal,
        ])
    return "\n".join(lines)


def _create_pull_request(
    repo_url: str,
    pat: str,
    branch_name: str,
    base_branch: str,
    title: str,
    body: str,
) -> tuple[str | None, str | None]:
    """Open a pull request on GitHub or Azure DevOps for the AAF branch."""
    provider = _repo_provider(repo_url)
    if provider == "github":
        owner, repo = _parse_github_repo(repo_url)
        payload = {
            "title": title,
            "head": branch_name,
            "base": base_branch,
            "body": body,
            "maintainer_can_modify": True,
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {pat}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Azure-Architecture-Factory",
        }
        response, error = _http_json_request(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            method="POST",
            headers=headers,
            payload=payload,
        )
        if error:
            return None, error
        return str((response or {}).get("html_url") or ""), None

    if provider == "azure-devops":
        org, project, repo = _parse_azure_devops_repo(repo_url)
        basic = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
        payload = {
            "sourceRefName": f"refs/heads/{branch_name}",
            "targetRefName": f"refs/heads/{base_branch}",
            "title": title,
            "description": body,
        }
        headers = {
            "Authorization": f"Basic {basic}",
            "User-Agent": "Azure-Architecture-Factory",
        }
        response, error = _http_json_request(
            f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests?api-version=7.1",
            method="POST",
            headers=headers,
            payload=payload,
        )
        if error:
            return None, error
        links = (response or {}).get("_links") or {}
        web = links.get("web") or {}
        return str(web.get("href") or ""), None

    return None, f"Pull request creation is not supported for host: {_repo_provider(repo_url)}"


def _walk_repo_for_analysis(repo_dir: str) -> dict:
    """Walk a cloned repository and extract analysis data.

    Returns a dict with:
    - ``readme``:      content of the root README (truncated)
    - ``arch_files``:  list of ``{name, content}`` dicts for architecture files
    - ``tech_stack``:  list of manifest filenames detected
    - ``file_counts``: dict mapping language name -> file count
    - ``dir_tree``:    list of top-level entry names
    """
    root = pathlib.Path(repo_dir)
    result: dict = {
        "readme": "",
        "arch_files": [],
        "tech_stack": [],
        "file_counts": {},
        "dir_tree": [],
    }

    # Top-level directory tree (skip dotfiles / .git)
    result["dir_tree"] = sorted(
        p.name for p in root.iterdir()
        if not p.name.startswith(".")
    )

    # README detection (case-insensitive priority order)
    for name in ("README.md", "README.rst", "README.txt", "readme.md", "Readme.md"):
        readme_path = root / name
        if readme_path.is_file():
            try:
                result["readme"] = readme_path.read_text(encoding="utf-8", errors="replace")[:_MAX_REPO_FILE_READ_BYTES]
            except Exception:
                pass
            break

    # Tech-stack manifest detection (top-level only for patterns, recursive for globs)
    seen_manifests: set[str] = set()
    for pattern in _MANIFEST_GLOBS:
        for match in root.glob(pattern):
            if match.is_file() and match.name not in seen_manifests:
                seen_manifests.add(match.name)
                result["tech_stack"].append(match.name)

    # Architecture file detection (recursive, max 10 files)
    arch_files_found = 0
    for p in sorted(root.rglob("*")):
        if arch_files_found >= 10:
            break
        if not p.is_file():
            continue
        # Skip .git directory
        if ".git" in p.parts:
            continue
        lower_stem = p.stem.lower()
        lower_suffix = p.suffix.lower()
        is_arch = (
            any(kw in lower_stem for kw in _ARCH_KEYWORDS)
            and lower_suffix in {".md", ".drawio", ".puml", ".plantuml", ".dsl", ".yaml", ".yml", ".json"}
        ) or lower_suffix == ".drawio"
        if is_arch:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")[:_MAX_REPO_FILE_READ_BYTES]
                result["arch_files"].append({"name": str(p.relative_to(root)), "content": content})
                arch_files_found += 1
            except Exception:
                pass

    # Code inventory by language
    counts: dict[str, int] = {}
    for p in root.rglob("*"):
        if ".git" in p.parts:
            continue
        lang = _CODE_EXTENSIONS.get(p.suffix.lower())
        if lang and p.is_file():
            counts[lang] = counts.get(lang, 0) + 1
    result["file_counts"] = dict(
        sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:20]
    )
    return result


def _build_repo_analysis_report(repo_url: str, branch_name: str, analysis: dict) -> str:
    """Build a structured Markdown analysis report for a cloned repository."""
    lines: list[str] = [
        "# Repository Analysis Report",
        "",
        f"**Repository**: {repo_url}  ",
        f"**Branch**: `{branch_name}`  ",
        f"**Generated**: {_utcnow_iso()}  ",
        "**Tool**: Azure Architecture Factory — automated analysis",
        "",
    ]

    # Repository structure
    if analysis.get("dir_tree"):
        lines += ["## Repository Structure", ""]
        lines += [f"- `{d}`" for d in analysis["dir_tree"][:30]]
        lines.append("")

    # Tech stack
    if analysis.get("tech_stack"):
        lines += ["## Tech Stack Detected", ""]
        lines += [f"- `{name}`" for name in sorted(analysis["tech_stack"])]
        lines.append("")

    # File inventory table
    if analysis.get("file_counts"):
        lines += ["## Code Inventory", "", "| Language | Files |", "|----------|-------|"]
        for lang, count in analysis["file_counts"].items():
            lines.append(f"| {lang} | {count} |")
        lines.append("")

    # README content (collapsible)
    if analysis.get("readme"):
        readme_preview = analysis["readme"][:3000].strip()
        lines += [
            "## README Summary",
            "",
            "<details><summary>Click to expand</summary>",
            "",
            readme_preview,
            "",
            "</details>",
            "",
        ]

    # Architecture files — run the existing parsers for each
    for af in analysis.get("arch_files", []):
        lines += [f"## Architecture: `{af['name']}`", ""]
        ext = pathlib.Path(af["name"]).suffix.lower()
        source_type_map = {
            ".drawio": "drawio",
            ".puml": "plantuml",
            ".plantuml": "plantuml",
            ".dsl": "structurizr",
        }
        source_type = source_type_map.get(ext)
        if not source_type:
            snippet = af["content"][:200].lower()
            if "@startuml" in snippet:
                source_type = "plantuml"
            elif "graph " in snippet or "flowchart " in snippet:
                source_type = "mermaid"
            elif "<mxgraphmodel" in snippet or "<mxfile" in snippet:
                source_type = "drawio"
            elif "workspace {" in snippet:
                source_type = "structurizr"
            elif ext == ".md":
                source_type = "architecture-markdown"
            else:
                source_type = "yaml"
        summary = _summarize_architecture_source(source_type, af["content"])
        if summary["components"]:
            lines += ["**Components:**", ""]
            lines += [f"- {c}" for c in summary["components"]]
            lines.append("")
        if summary["relationships"]:
            lines += ["**Relationships:**", ""]
            lines += [f"- {r}" for r in summary["relationships"]]
            lines.append("")
        if summary["signals"]:
            lines += [f"*Parsing: {', '.join(summary['signals'])}*", ""]

    lines += [
        "---",
        "",
        "> This report was generated automatically by the Azure Architecture Factory.",
        "> Review and amend before merging to your main branch.",
        "",
    ]
    return "\n".join(lines)


def _commit_and_push_report(
    repo_dir: str,
    report_content: str,
    branch_name: str,
    push_url: str,
) -> tuple[bool, str]:
    """Write the analysis report, commit it, and push.  Returns ``(success, error_msg)``."""
    report_path = pathlib.Path(repo_dir) / _AAF_ANALYSIS_REPORT_FILE
    try:
        report_path.write_text(report_content, encoding="utf-8")
    except Exception as exc:
        return False, f"Failed to write report file: {exc}"
    _git_run(["add", _AAF_ANALYSIS_REPORT_FILE], cwd=repo_dir, timeout=15)
    _, stderr, rc = _git_run(
        ["commit", "-m", "chore: add AAF automated repository analysis report"],
        cwd=repo_dir,
        timeout=15,
    )
    if rc != 0:
        return False, f"git commit failed: {stderr.strip()[:300]}"
    _, stderr, rc = _git_run(
        ["push", push_url, f"{branch_name}:{branch_name}"],
        cwd=repo_dir,
        timeout=30,
    )
    if rc != 0:
        return False, f"git push failed: {_mask_pat_in_text(stderr).strip()[:400]}"
    return True, ""


def _validate_target_project_slug(raw_slug: object) -> tuple[str | None, str | None]:
    """Validate an optional project slug selected for iterative regeneration."""
    if raw_slug in (None, ""):
        return None, None
    slug = _sanitize_project_slug(raw_slug)
    if not slug:
        return None, "targetProjectSlug contains invalid characters"
    manifest_path = FACTORY_REPO_ROOT / "projects" / slug / "project-manifest.json"
    if not manifest_path.is_file():
        return None, f"Project slug '{slug}' was not found"
    return slug, None


def _build_generation_options(
    fields: dict[str, object],
    *,
    file_name: str = "",
    content: str = "",
    uploaded_file_name: str = "",
    raw_bytes: bytes | None = None,
) -> tuple[dict[str, object], str | None]:
    """Normalize intake options shared by JSON and multipart paths."""
    requested_source_type = _sanitize_source_type(fields.get("sourceType") or "auto")
    detected_source_type = _detect_source_type(
        file_name=file_name,
        content=content,
        uploaded_file_name=uploaded_file_name,
        raw_bytes=raw_bytes,
    )
    generation_options: dict[str, object] = {
        "enableObservability": _coerce_bool(fields.get("enableObservability"), default=True),
        "generateInfra": _coerce_bool(fields.get("generateInfra"), default=True),
        "runSecurityAudit": _coerce_bool(fields.get("runSecurityAudit"), default=True),
        "networkTier": _sanitize_network_tier(fields.get("networkTier", "public")),
        "sourceType": detected_source_type if requested_source_type == "auto" else requested_source_type,
        "sourceTypeRequested": requested_source_type,
        "sourceTypeDetected": detected_source_type,
    }
    impl_lang = _sanitize_implementation_language(fields.get("implementationLanguage"))
    if impl_lang:
        generation_options["implementationLanguage"] = impl_lang
    iac_tool = str(fields.get("iacTool") or "").strip().lower()
    if iac_tool:
        generation_options["iacTool"] = iac_tool
    deployment_mode = _sanitize_deployment_mode(fields.get("deploymentMode"))
    if deployment_mode == "aca-express":
        generation_options["deploymentMode"] = "aca-express"
        generation_options["acaExpressRegion"] = _sanitize_aca_express_region(fields.get("acaExpressRegion"))
        raw_image = str(fields.get("acaExpressImage") or "").strip()
        if raw_image:
            generation_options["acaExpressImage"] = raw_image
    target_project_slug, slug_error = _validate_target_project_slug(fields.get("targetProjectSlug"))
    if slug_error:
        return {}, slug_error
    if target_project_slug:
        generation_options["targetProjectSlug"] = target_project_slug
    return generation_options, None


def _save_source_attachment(
    intake_dir: pathlib.Path,
    canonical_file_name: str,
    source_type: str,
    uploaded_file_name: str,
    raw_bytes: bytes,
) -> str:
    """Persist the uploaded architecture artifact for traceability."""
    attachments_dir = intake_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    raw_name = pathlib.Path(uploaded_file_name or "source.bin").name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", pathlib.Path(canonical_file_name).stem).strip("-.") or "source"
    suffix = pathlib.Path(raw_name).suffix or ".bin"
    safe_name = f"{stem}-{source_type}{suffix.lower()}"
    attachment_path = attachments_dir / safe_name
    attachment_path.write_bytes(raw_bytes)
    return f"docs/intake/attachments/{safe_name}"


def _build_generation_document(file_name: str, content: str, generation_options: dict[str, object] | None = None) -> str:
    """Wrap non-BRD sources into a canonical markdown document for the runner."""
    generation_options = generation_options or {}
    source_type = _sanitize_source_type(generation_options.get("sourceType"))
    if source_type == "brd-markdown":
        return content

    title_hint = pathlib.Path(file_name).stem.replace("-", " ").replace("_", " ").strip().title() or "Architecture Intake"
    source_file_name = str(generation_options.get("sourceFileName") or file_name)
    source_attachment = str(generation_options.get("sourceAttachment") or "").strip()
    target_project_slug = str(generation_options.get("targetProjectSlug") or "").strip()
    fence_language = _SOURCE_TYPE_FENCE_LANGUAGES.get(source_type, "text")
    parsed_summary = _summarize_architecture_source(source_type, content)

    lines = [
        f"# {title_hint}",
        "",
        "## Intake Mode",
        f"- source_type: {source_type}",
        f"- source_file: {source_file_name}",
        f"- target_project_slug: {target_project_slug or '(new project)'}",
    ]
    if source_attachment:
        lines.append(f"- source_attachment: {source_attachment}")
    lines.extend(
        [
            "",
            "## Generation Instructions",
            "- Treat the supplied architecture artifact as the source of truth for the system design.",
            "- Generate or update architecture docs, starter source code, tests, and Azure infrastructure from this input.",
            "- Keep selected implementation language and infrastructure tool overrides when they were explicitly chosen.",
            "- Surface assumptions and unresolved gaps when the source is underspecified.",
            "- Update the existing project in place instead of creating a new one." if target_project_slug else "- Create a new project baseline from this source.",
            "",
        ]
    )
    if generation_options and generation_options.get("deploymentMode") == "aca-express":
        aca_region = generation_options.get("acaExpressRegion", "westcentralus")
        aca_image = generation_options.get("acaExpressImage", "")
        lines.extend([
            "## Deployment Mode",
            "- deployment_mode: aca-express",
            f"- aca_express_region: {aca_region}",
        ])
        if aca_image:
            lines.append(f"- aca_express_image: {aca_image}")
        lines.extend([
            "- Skip Phase 3 Bicep/Terraform infrastructure generation (generate_infra is overridden to false).",
            "- Invoke aca-express-deployer agent for Phase 5 deployment instead of the standard deployer.",
            "- ACA Express preview constraints: HTTP-only workloads, westcentralus / eastasia regions only.",
            "  No VNet, Managed Identity, Key Vault, Dapr, KEDA, custom domains, or CORS configuration.",
            "",
        ])
    lines.extend(
        [
            "## Parsed Architecture Summary",
        ]
    )
    if parsed_summary["components"]:
        lines.append("### Components")
        lines.extend([f"- {item}" for item in parsed_summary["components"]])
    if parsed_summary["relationships"]:
        lines.append("### Relationships")
        lines.extend([f"- {item}" for item in parsed_summary["relationships"]])
    if parsed_summary["signals"]:
        lines.append("### Parsing Signals")
        lines.extend([f"- {item}" for item in parsed_summary["signals"]])
    if not any(parsed_summary.values()):
        lines.append("- No structured summary could be extracted; use the raw source below.")
    lines.extend(
        [
            "",
            "## Architecture Source",
        ]
    )
    if source_type in _REFERENCE_ONLY_SOURCE_TYPES:
        lines.extend(
            [
                "The uploaded artifact is stored as a reference attachment. Use the summary below as the working source.",
                "",
                content.strip(),
            ]
        )
    else:
        lines.extend([f"```{fence_language}", content.rstrip(), "```"])
    lines.append("")
    return "\n".join(lines)


def _validate_brd_content(raw: object) -> tuple[str | None, str | None]:
    """Validate a BRD content payload.

    Returns ``(content, None)`` on success or ``(None, error_message)`` on
    failure. Enforces: must be a string, UTF-8 decodable (already, since we
    got a str), no NUL or other C0 control bytes (except tab/newline/CR),
    and within the configured min/max length bounds after stripping.
    """
    if not isinstance(raw, str):
        return None, "content must be a string"
    content = raw.strip()
    if not content:
        return None, "content is empty"
    # Reject embedded NUL and other C0 control characters that are neither
    # whitespace nor standard line terminators. These frequently appear in
    # obfuscated payloads and can break downstream tooling.
    for ch in content:
        code = ord(ch)
        if code < 0x20 and ch not in ("\t", "\n", "\r"):
            return None, "content contains disallowed control characters"
    if len(content) < MIN_BRD_CONTENT_CHARS:
        return None, f"BRD content too short (min {MIN_BRD_CONTENT_CHARS} characters)"
    if len(content) > MAX_BRD_CONTENT_CHARS:
        return None, f"BRD content too long (max {MAX_BRD_CONTENT_CHARS} characters)"
    return content, None


class FactoryPortalHandler(SimpleHTTPRequestHandler):
    """HTTP handler for factory portal with BRD intake API"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FACTORY_REPO_ROOT), **kwargs)

    def _current_user(self) -> str | None:
        """Return the authenticated user's UPN from Easy Auth headers, or None.

        Container Apps Easy Auth forwards two headers on every authenticated
        request:
          X-MS-CLIENT-PRINCIPAL-NAME → identity "name" (sometimes display name,
                                       sometimes UPN — depends on the token)
          X-MS-CLIENT-PRINCIPAL      → base64-encoded JSON principal with full
                                       claim list.
        Because X-MS-CLIENT-PRINCIPAL-NAME can be a display name like
        "MOD Administrator" rather than an email, we prefer the
        preferred_username / upn / email claim from the decoded principal,
        and only fall back to the header if those are absent.
        """
        principal = self._decoded_principal()
        if principal:
            # Prefer claims in a deterministic priority order so that for B2B
            # guests we land on the user's original email (preferred_username /
            # email) rather than the mangled `user_domain.com#EXT#@tenant` UPN.
            claim_priority = [
                "preferred_username",
                "email",
                "emails",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "upn",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
            ]
            by_type: dict[str, str] = {}
            for claim in principal.get("claims") or []:
                typ = (claim.get("typ") or claim.get("type") or "").lower()
                val = claim.get("val") or claim.get("value")
                if typ and val and "@" in str(val) and typ not in by_type:
                    by_type[typ] = str(val).strip()
            for typ in claim_priority:
                if typ in by_type:
                    return by_type[typ]
            # Some principals expose the UPN at top-level.
            for key in ("userPrincipalName", "userDetails"):
                val = principal.get(key)
                if val and "@" in str(val):
                    return str(val).strip()
        upn = self.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        if upn and "@" in upn:
            return upn.strip()
        return None

    def _decoded_principal(self) -> dict | None:
        """Decode X-MS-CLIENT-PRINCIPAL once per request; cache on the handler."""
        cached = getattr(self, "_cached_principal", False)
        if cached is not False:
            return cached  # may be None
        raw = self.headers.get("X-MS-CLIENT-PRINCIPAL")
        principal: dict | None = None
        if raw:
            try:
                padded = raw + "=" * (-len(raw) % 4)
                decoded = json.loads(base64.b64decode(padded).decode("utf-8"))
                if isinstance(decoded, dict):
                    principal = decoded
            except Exception:
                principal = None
        self._cached_principal = principal
        return principal

    def _current_tenant(self) -> str | None:
        """Return the user's home tenant id (the 'tid' claim) from Easy Auth.

        Easy Auth forwards a base64-encoded JSON principal in
        X-MS-CLIENT-PRINCIPAL. We decode it and pluck the 'tid' claim so we
        can enforce a per-deployment tenant allowlist independently of the
        app registration's sign-in audience.
        """
        principal = self._decoded_principal()
        if not principal:
            return None
        for claim in principal.get("claims") or []:
            typ = (claim.get("typ") or claim.get("type") or "").lower()
            if typ in {"tid", "http://schemas.microsoft.com/identity/claims/tenantid"}:
                val = claim.get("val") or claim.get("value")
                if val:
                    return str(val).strip().lower()
        return None

    def _tenant_allowed(self) -> bool:
        """True when no tenant allowlist is configured, or the request's tenant is in it."""
        if ALLOWED_TENANTS is None:
            return True
        tid = self._current_tenant()
        return bool(tid) and tid in ALLOWED_TENANTS

    def _authorized_user(self) -> str | None:
        """Return the current user only when tenant policy allows them.

        Users from disallowed tenants are treated as anonymous — they cannot
        see any project. This is enforced above Easy Auth, so even if a guest
        account from another tenant successfully signs in, they still get
        zero access.
        """
        if not self._tenant_allowed():
            return None
        return self._current_user()

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        request_path = parsed.path

        if request_path == "/":
            self.send_response(302)
            self.send_header("Location", "/factory-portal.html")
            self.end_headers()
            return

        if request_path in PORTAL_PATH_ALIASES:
            self.send_response(302)
            self.send_header("Location", "/factory-portal.html")
            self.end_headers()
            return

        if request_path == "/health":
            return self._handle_health()

        if request_path == "/api/resilience":
            return self._handle_resilience_metrics()

        if request_path == "/api/me":
            user = self._current_user()
            tenant = self._current_tenant()
            return self._send_json({
                "authMode": AUTH_MODE or "none",
                "authenticated": bool(user),
                "user": user,
                "tenantId": tenant,
                "tenantAllowed": self._tenant_allowed(),
                "isAdmin": _is_admin(user) and self._tenant_allowed(),
            }, 200)

        # Hard-deny requests whose token 'tid' is not in the tenant allowlist.
        # /api/me, /health, /ready, /api/resilience, and the login/logout endpoints are exempt
        # so probes and the user can see a friendly message and sign out.
        # Static browser assets (css/js/images) stay accessible to avoid
        # breaking the error page.
        if (AUTH_MODE == "entra"
                and ALLOWED_TENANTS is not None
                and not self._tenant_allowed()
                and not request_path.startswith(("/.auth/", "/api/me", "/health",
                                                  "/ready", "/api/resilience",
                                                  "/assets/", "/favicon"))
                and request_path != "/factory-portal.html"):
            if request_path.startswith("/api/") or request_path.endswith(".json"):
                return self._send_json({"error": "Tenant not authorized for this portal."}, 403)
            self.send_response(403)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<!doctype html><meta charset='utf-8'><title>Access denied</title>"
                b"<body style='font-family:Segoe UI,sans-serif;padding:3rem;max-width:640px'>"
                b"<h1>Access denied</h1>"
                b"<p>This portal is restricted to specific Microsoft Entra tenants. "
                b"Your account is authenticated, but your home tenant is not in the "
                b"allowlist for this deployment.</p>"
                b"<p><a href='/.auth/logout'>Sign out</a> and try a different account.</p>"
                b"</body>")
            return

        if request_path == "/ready":
            return self._handle_ready()

        if request_path in {"/api/brd-runs", "/api/runs"}:
            return self._handle_runs_list()

        if request_path == "/api/agent-foundry/runs":
            return self._handle_agent_foundry_runs_list()

        if request_path == "/api/csa-copilot/tools":
            if not self._require_auth_for_mutation():
                return
            return self._handle_csa_copilot_tools()

        if request_path == "/api/application-zone/packs":
            return self._handle_application_zone_packs()

        if request_path == "/api/application-zone/aapaas/summary":
            return self._handle_aapaas_summary()

        if request_path == "/api/application-zone/security-control-tower/work-board":
            return self._handle_security_control_tower_work_board()

        if request_path == "/api/application-zone/security-control-tower/tool-integrations":
            return self._handle_security_control_tower_tool_integrations()

        if request_path == "/api/application-zone/security-control-tower/approval-workflows":
            return self._handle_security_control_tower_approval_workflows()

        if request_path == "/api/application-zone/security-control-tower/pilot-readiness":
            return self._handle_security_control_tower_pilot_readiness()

        if request_path == "/api/application-zone/security-control-tower/connector-pilot":
            return self._handle_security_control_tower_connector_pilot()

        if request_path == "/api/application-zone/security-control-tower/pilot-evidence":
            return self._handle_security_control_tower_pilot_evidence()

        appzone_match = re.fullmatch(r"/api/application-zone/packs/([^/]+)/versions", request_path)
        if appzone_match:
            return self._handle_application_zone_pack_versions(appzone_match.group(1))

        appzone_version_match = re.fullmatch(
            r"/api/application-zone/packs/([^/]+)/versions/([^/]+)",
            request_path,
        )
        if appzone_version_match:
            return self._handle_application_zone_pack_manifest(
                appzone_version_match.group(1),
                appzone_version_match.group(2),
            )

        appzone_instance_match = re.fullmatch(
            r"/api/application-zone/instances/([^/]+)(?:/(.*))?",
            request_path,
        )
        if appzone_instance_match:
            if not self._require_auth_for_mutation():
                return
            return self._handle_application_zone_instance_action(
                appzone_instance_match.group(1),
                appzone_instance_match.group(2) or "",
            )

        if (
            request_path.startswith("/api/brd-runs/")
            or request_path.startswith("/api/runs/")
        ) and request_path.endswith("/project"):
            run_id = request_path.split("/")[-2]
            return self._handle_run_project(run_id)

        if (
            request_path.startswith("/api/brd-runs/")
            or request_path.startswith("/api/runs/")
        ) and request_path.endswith("/log"):
            run_id = request_path.split("/")[-2]
            return self._handle_run_log(run_id)

        if request_path.startswith("/api/brd-runs/") or request_path.startswith("/api/runs/"):
            run_id = request_path.split("/")[-1]
            return self._handle_run_status(run_id)

        if request_path.startswith("/api/agent-foundry/runs/"):
            run_id = request_path.split("/")[-1]
            return self._handle_agent_foundry_run_status(run_id)

        if request_path.startswith("/api/project-analysis/"):
            slug = request_path.split("/")[-1]
            return self._handle_project_analysis(slug)

        if request_path.startswith("/api/project-operations/"):
            slug = request_path.split("/")[-1]
            return self._handle_project_operations(slug)

        if request_path.startswith("/api/projects/") and request_path.endswith("/files"):
            if not self._require_auth_for_mutation():
                return
            slug = request_path.split("/")[-2]
            return self._handle_project_files(slug)

        if request_path.startswith("/api/projects/") and request_path.endswith("/download"):
            if not self._require_auth_for_mutation():
                return
            slug = request_path.split("/")[-2]
            return self._handle_project_download(slug)

        if request_path.startswith("/api/projects/") and request_path.endswith("/file"):
            if not self._require_auth_for_mutation():
                return
            slug = request_path.split("/")[-2]
            return self._handle_project_file_preview(slug, parsed.query)

        if request_path == "/factory-projects.generated.json":
            return self._serve_json_feed()

        # Block direct browsing of the scripts directory (internal tooling only)
        if request_path.startswith("/scripts/") or request_path == "/scripts":
            self.send_error(403, "Forbidden")
            return

        # Enforce per-deployment project visibility for direct /projects/<slug>/...
        # file access. When an allowlist is configured, hidden slugs return 404.
        if request_path.startswith("/projects/"):
            parts = request_path.split("/", 3)  # ['', 'projects', '<slug>', 'rest...']
            if len(parts) >= 3 and parts[2]:
                if not _user_can_see_project(parts[2], self._authorized_user()):
                    self.send_error(404, "Not Found")
                    return

        if request_path == "/api/admin/tokens":
            if not self._require_admin_key():
                return
            return self._handle_token_list()

        if request_path == "/api/admin/token-requests":
            if not self._require_admin_key():
                return
            return self._handle_token_request_list()

        if request_path == "/api/admin/project-owners":
            if not self._require_admin_key():
                return
            return self._handle_project_owners_list(parsed.query)

        if request_path == "/api/admin/brd-allowlist":
            if not self._require_brd_admin():
                return
            return self._handle_brd_allowlist_list()

        # Copilot CLI runs — per-project endpoints.
        # GET /api/projects/<slug>/copilot-runtime    -> availability + config
        # GET /api/projects/<slug>/copilot-runs       -> list runs
        # GET /api/projects/<slug>/copilot-runs/<id>  -> single run status
        # GET /api/projects/<slug>/copilot-runs/<id>/log -> tail log
        if request_path.startswith("/api/projects/") and "/copilot" in request_path:
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_get(request_path)

        # Repo-root Copilot CLI endpoints (not scoped to any project).
        # GET /api/copilot-runtime
        # GET /api/copilot-agents
        # GET /api/copilot-runs[/<id>[/log|/diff]]
        if (
            request_path == "/api/copilot-runtime"
            or request_path == "/api/copilot-agents"
            or request_path == "/api/copilot-runs"
            or request_path.startswith("/api/copilot-runs/")
        ):
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_root_get(request_path)

        # Serve factory-templates/ files dynamically
        if request_path.startswith("/factory-templates/"):
            return self._serve_factory_template_file(request_path)

        # Default file serving
        return super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        path = urlparse(self.path).path
        if path == "/api/brd-intake":
            if not self._require_auth_for_mutation():
                return
            if not self._require_brd_intake_principal():
                return
            return self._handle_brd_intake()
        if path == "/api/brd-upload":
            if not self._require_auth_for_mutation():
                return
            if not self._require_brd_intake_principal():
                return
            return self._handle_brd_upload()
        if path == "/api/repo-intake":
            if not self._require_auth_for_mutation():
                return
            if not self._require_brd_intake_principal():
                return
            return self._handle_repo_intake()
        if path == "/api/agent-foundry/runs":
            if not self._require_auth_for_mutation():
                return
            if not self._require_brd_intake_principal():
                return
            return self._handle_agent_foundry_run_create()
        if path.startswith("/api/agent-foundry/runs/") and path.endswith("/approve"):
            if not self._require_auth_for_mutation():
                return
            if not self._require_brd_intake_principal():
                return
            run_id = path.split("/")[-2]
            return self._handle_agent_foundry_run_approve(run_id)
        if path == "/api/admin/issue-token":
            if not self._require_admin_key():
                return
            return self._handle_issue_token()
        if path == "/api/admin/project-owners":
            if not self._require_admin_key():
                return
            return self._handle_project_owners_update()
        if path == "/api/admin/brd-allowlist":
            if not self._require_brd_admin():
                return
            return self._handle_brd_allowlist_update()
        if path == "/api/token-request":
            return self._handle_submit_token_request()
        if path == "/api/csa-copilot/ask":
            if not self._require_auth_for_mutation():
                return
            return self._handle_csa_copilot_ask()
        if path == "/api/application-zone/validate-inputs":
            return self._handle_application_zone_validate_inputs()
        if path == "/api/application-zone/instances":
            if not self._require_auth_for_mutation():
                return
            return self._handle_application_zone_create_instance()
        appzone_runtime_match = re.fullmatch(
            r"/api/application-zone/instances/([^/]+)(?:/(.*))?",
            path,
        )
        if appzone_runtime_match:
            if not self._require_auth_for_mutation():
                return
            return self._handle_application_zone_instance_action(
                appzone_runtime_match.group(1),
                appzone_runtime_match.group(2) or "",
            )
        if path == "/api/brd-chat":
            if not self._require_auth_for_mutation():
                return
            return self._handle_brd_chat()
        if path.startswith("/api/projects/") and path.endswith("/chat"):
            if not self._require_auth_for_mutation():
                return
            # path = /api/projects/<slug>/chat
            parts = path.split("/")
            if len(parts) == 5 and parts[3]:
                return self._handle_project_chat(parts[3])
            self._send_json({"error": "Invalid project chat path"}, 400)
            return
        if path == "/api/guide/refresh":
            if not self._require_auth_for_mutation():
                return
            return self._handle_guide_refresh()

        # Copilot CLI runs — per-project endpoints.
        # POST /api/projects/<slug>/copilot-runs           -> start run
        # POST /api/projects/<slug>/copilot-runs/<id>/cancel -> cancel
        if path.startswith("/api/projects/") and "/copilot-runs" in path:
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_post(path)

        # Repo-root Copilot CLI endpoints.
        # POST /api/copilot-runs                 -> start run at repo root
        # POST /api/copilot-runs/<id>/cancel     -> cancel
        if path == "/api/copilot-runs" or path.startswith("/api/copilot-runs/"):
            if not self._require_auth_for_mutation():
                return
            return self._handle_copilot_root_post(path)

        self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key, Authorization")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _require_auth_for_mutation(self) -> bool:
        """Require Entra ID bearer token, issued token, or master API key.

        Auth precedence:
        1. If Entra ID env vars are set → validate Bearer token
           (or, if TRUST_EASYAUTH_HEADERS=1, accept EasyAuth's forwarded
           X-MS-CLIENT-PRINCIPAL-* headers from the browser session)
        2. Else if API key env var is set:
           a. X-Factory-Api-Key contains a '.' → treat as issued token (HMAC-signed, expirable, usage-counted)
           b. Otherwise → compare directly as master key
        3. If neither is set → allow (local development mode)
        """
        # --- Entra ID (preferred) ---
        if _jwks_cache is not None:
            # Defense-in-depth: if EasyAuth is in front and has already
            # validated the browser session, it forwards principal headers
            # that a forged caller cannot inject (EasyAuth strips incoming
            # copies before forwarding). Trust them only when explicitly
            # opted in.
            if TRUST_EASYAUTH_HEADERS:
                principal_id = self.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "").strip()
                principal_idp = self.headers.get("X-MS-CLIENT-PRINCIPAL-IDP", "").strip().lower()
                if principal_id and principal_idp in ("aad", "azureactivedirectory"):
                    principal_name = self.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "").strip()
                    self._entra_claims = {
                        "oid": principal_id,
                        "preferred_username": principal_name,
                        "source": "easyauth",
                    }
                    return True

            auth_header = self.headers.get("Authorization", "")
            if not auth_header:
                self._send_json(
                    {"error": "Missing Authorization header. Provide a Bearer token."},
                    401,
                )
                return False
            result = _validate_entra_token(auth_header, _jwks_cache)
            if isinstance(result, str):
                self._send_json({"error": result}, 401)
                return False
            self._entra_claims = result
            return True

        # --- Issued token or master API key ---
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if not expected_key:
            return True  # No auth configured — local dev mode

        provided = self.headers.get("X-Factory-Api-Key", "")
        if not provided:
            self._send_json({"error": "Unauthorized"}, 401)
            return False

        # Issued tokens contain exactly one '.' (b64payload.hmac_hex)
        if provided.count(".") == 1:
            result = _validate_issued_token(provided)
            if isinstance(result, str):
                self._send_json({"error": result}, 401)
                return False
            if result is None:
                # Dot in string but not a valid issued-token format — fall through to master key check
                pass
            else:
                return True

        # Master key comparison
        if not hmac.compare_digest(provided, expected_key):
            self._send_json({"error": "Unauthorized"}, 401)
            return False
        return True

    def _require_admin_key(self) -> bool:
        """Require the master API key (not an issued token) for admin operations."""
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if not expected_key:
            return True  # No auth — local dev mode
        provided = self.headers.get("X-Factory-Api-Key", "")
        if not hmac.compare_digest(provided, expected_key):
            self._send_json({"error": "Admin access requires master API key"}, 403)
            return False
        return True

    def _require_brd_intake_principal(self) -> bool:
        """Enforce BRD allowlist (env seed + file overlay) against the authenticated caller.

        Must be called AFTER `_require_auth_for_mutation`, so `self._entra_claims`
        is populated. If the effective allowlist is empty, any authenticated user is allowed.
        """
        effective = _current_brd_allowlist()
        if not effective:
            return True  # No allowlist configured

        if self._caller_principals() & effective:
            return True

        self._send_json(
            {"error": "BRD intake is restricted. Contact an admin to be added to the allowlist."},
            403,
        )
        return False

    def _caller_principals(self) -> set[str]:
        """Lowercased identifiers that can match an allowlist entry."""
        claims = getattr(self, "_entra_claims", None) or {}
        values = {
            str(claims.get("preferred_username", "")).strip().lower(),
            str(claims.get("upn", "")).strip().lower(),
            str(claims.get("email", "")).strip().lower(),
            str(claims.get("oid", "")).strip().lower(),
            str(claims.get("sub", "")).strip().lower(),
        }
        values.discard("")
        return values

    def _require_brd_admin(self) -> bool:
        """Allow BRD allowlist management for: master API key, portal admins,
        OR any user already on the BRD allowlist (bootstraps self-service)."""
        # Master key still works
        expected_key = os.environ.get(API_KEY_ENV, "").strip()
        if expected_key:
            provided = self.headers.get("X-Factory-Api-Key", "")
            if provided and hmac.compare_digest(provided, expected_key):
                return True

        # Require auth if Entra is configured
        if _jwks_cache is not None:
            if not self._require_auth_for_mutation():
                return False
            caller = self._caller_principals()
            # Portal-level admins
            for principal in caller:
                if _is_admin(principal):
                    return True
            # Current allowlist members can manage the list
            if caller & _current_brd_allowlist():
                return True
            self._send_json(
                {
                    "error": "Only portal admins or current BRD allowlist members can manage the allowlist.",
                    "yourPrincipals": sorted(caller),
                    "currentAllowlist": sorted(_current_brd_allowlist()),
                    "hint": "Ask an admin to add one of 'yourPrincipals' to BRD_INTAKE_ALLOWED_PRINCIPALS env var or FACTORY_PORTAL_ADMINS.",
                },
                403,
            )
            return False
        # No auth configured — local dev
        return True

    def _handle_issue_token(self):
        """POST /api/admin/issue-token — create a signed, usage-counted token."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        sub = str(payload.get("sub", "")).strip()
        purpose = str(payload.get("purpose", "manual")).strip() or "manual"
        try:
            ttl_seconds = int(payload.get("ttl_seconds", 86400))
            max_uses = int(payload.get("max_uses", 5))
        except (TypeError, ValueError):
            self._send_json({"error": "ttl_seconds and max_uses must be integers"}, 400)
            return

        if ttl_seconds < 0 or ttl_seconds > 60 * 60 * 24 * 3650:  # 0 = never; max 10 years
            self._send_json({"error": "ttl_seconds must be 0 (never expires) or 1–315360000 (max 10 years)"}, 400)
            return
        if max_uses < 0 or max_uses > 10000:
            self._send_json({"error": "max_uses must be between 0 and 10000"}, 400)
            return

        try:
            result = _issue_token(sub, ttl_seconds, max_uses, purpose)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 500)
            return

        self._send_json(result, 201)

    def _handle_token_request_list(self):
        """GET /api/admin/token-requests — return all pending token requests."""
        with _TOKEN_REQUESTS_LOCK:
            requests_copy = list(_TOKEN_REQUESTS)
        self._send_json({"requests": requests_copy})

    def _handle_submit_token_request(self):
        """POST /api/token-request — public endpoint, no auth required."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        sub = str(payload.get("sub", "")).strip()
        reason = str(payload.get("reason", "")).strip()
        if not sub:
            self._send_json({"error": "sub (name or email) is required"}, 400)
            return

        # Enforce a simple request-rate limit: max 3 pending requests per sub
        with _TOKEN_REQUESTS_LOCK:
            pending_from_sub = sum(
                1 for r in _TOKEN_REQUESTS
                if r["sub"].lower() == sub.lower() and r["status"] == "pending"
            )
            if pending_from_sub >= 3:
                self._send_json({"error": "Too many pending requests from this address"}, 429)
                return
            req_id = uuid.uuid4().hex[:12]
            _TOKEN_REQUESTS.append({
                "id": req_id,
                "sub": sub,
                "reason": reason[:500],
                "requested_at": time.time(),
                "status": "pending",
            })

        logger.info("Token request submitted: id=%s sub=%s", req_id, sub)
        _notify_teams_token_request(req_id, sub, reason)
        self._send_json({"ok": True, "id": req_id,
                         "message": "Request submitted. You will receive your token via the admin."})

    def _handle_token_list(self):
        """GET /api/admin/tokens — return all issued tokens and their usage counters."""
        now = time.time()
        with _ISSUED_TOKENS_LOCK:
            tokens = [
                {
                    "jti": jti,
                    "sub": entry["sub"],
                    "purpose": entry["purpose"],
                    "uses": entry["uses"],
                    "max_uses": entry["max_uses"],
                    "exp": entry["exp"],
                    "expired": entry["exp"] != 0 and entry["exp"] < now,
                }
                for jti, entry in _ISSUED_TOKENS.items()
            ]
        tokens.sort(key=lambda t: t["exp"], reverse=True)
        self._send_json({"tokens": tokens})

    def _handle_brd_allowlist_list(self):
        """GET /api/admin/brd-allowlist — effective allowlist + source breakdown."""
        env_seed = sorted(BRD_INTAKE_ALLOWED_PRINCIPALS)
        file_overlay = sorted(_load_brd_allowlist_file())
        effective = sorted(_current_brd_allowlist())
        self._send_json({
            "envSeed": env_seed,
            "fileOverlay": file_overlay,
            "effective": effective,
            "allowlistFile": str(BRD_ALLOWLIST_FILE),
            "note": "env seed is read-only (set BRD_INTAKE_ALLOWED_PRINCIPALS). file overlay is editable here.",
        })

    def _handle_brd_allowlist_update(self):
        """POST /api/admin/brd-allowlist — add/remove/set principals in the file overlay."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception as exc:
            self._send_json({"error": f"Invalid request: {exc}"}, 400)
            return

        action = str(payload.get("action", "add")).strip().lower() or "add"
        raw = payload.get("principals")
        if raw is None and "principal" in payload:
            raw = [payload.get("principal")]
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            raw = []
        cleaned = []
        for p in raw:
            if isinstance(p, str):
                norm = p.strip().lower()
                if norm and norm not in cleaned:
                    cleaned.append(norm)

        if action not in {"add", "remove", "set"}:
            self._send_json({"error": "action must be add, remove, or set"}, 400)
            return
        if action in {"add", "remove"} and not cleaned:
            self._send_json({"error": "principals list cannot be empty for add/remove"}, 400)
            return

        current = _load_brd_allowlist_file()
        if action == "add":
            current |= set(cleaned)
        elif action == "remove":
            current -= set(cleaned)
        else:
            current = set(cleaned)

        _save_brd_allowlist_file(current)
        self._send_json({
            "ok": True,
            "action": action,
            "fileOverlay": sorted(current),
            "effective": sorted(BRD_INTAKE_ALLOWED_PRINCIPALS | current),
        })

    # ---- Copilot CLI run handlers ---------------------------------------

    def _handle_copilot_get(self, request_path: str):
        """Route GET /api/projects/<slug>/copilot* paths."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        parts = request_path.split("/")
        # ['', 'api', 'projects', '<slug>', 'copilot-<suffix>', ...]
        if len(parts) < 5:
            self._send_json({"error": "Invalid copilot path"}, 400)
            return
        slug = parts[3]
        action = parts[4]

        project_root = self._resolve_project_root(slug)
        if project_root is None:
            self._send_json({"error": "Project not found"}, 404)
            return

        if action == "copilot-runtime" and len(parts) == 5:
            info = copilot_runner.runtime_info()
            self._send_json(info)
            return

        if action == "copilot-runs":
            if len(parts) == 5:
                runs = copilot_runner.list_runs(project_root)
                self._send_json({"slug": slug, "runs": runs})
                return
            # /copilot-runs/<runId>[/log|/diff]
            run_id = parts[5]
            if len(parts) == 6:
                run = copilot_runner.get_run(project_root, run_id)
                if run is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(run)
                return
            if len(parts) == 7 and parts[6] == "log":
                tail = copilot_runner.read_log_tail(project_root, run_id)
                if tail is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                body = tail.encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if len(parts) == 7 and parts[6] == "diff":
                diff = copilot_runner.diff_run(project_root, run_id)
                if diff is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(diff)
                return

        self._send_json({"error": "Invalid copilot path"}, 400)

    def _handle_copilot_post(self, path: str):
        """Route POST /api/projects/<slug>/copilot-runs[/<id>/cancel]."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        parts = path.split("/")
        # ['', 'api', 'projects', '<slug>', 'copilot-runs', ...]
        if len(parts) < 5:
            self._send_json({"error": "Invalid copilot path"}, 400)
            return
        slug = parts[3]
        project_root = self._resolve_project_root(slug)
        if project_root is None:
            self._send_json({"error": "Project not found"}, 404)
            return

        # Cancel: /copilot-runs/<runId>/cancel
        if len(parts) == 7 and parts[4] == "copilot-runs" and parts[6] == "cancel":
            run_id = parts[5]
            result = copilot_runner.cancel_run(project_root, run_id)
            if result is None:
                self._send_json({"error": "Run not found"}, 404)
                return
            self._send_json({"ok": True, "run": result})
            return

        # Start: /copilot-runs
        if len(parts) == 5 and parts[4] == "copilot-runs":
            content_length = self._safe_content_length()
            if content_length is None:
                return
            try:
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body) if body else {}
            except Exception as exc:
                self._send_json({"error": f"Invalid request: {exc}"}, 400)
                return

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send_json({"error": "prompt is required"}, 400)
                return

            model_raw = str(payload.get("model", "") or "").strip()
            session_raw = str(payload.get("sessionId", "") or "").strip()
            agent_raw = str(payload.get("agent", "") or "").strip()
            # Reject obviously unsafe values — model names are alnum + .- only,
            # session IDs are UUIDs.
            if model_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", model_raw):
                self._send_json({"error": "Invalid model name"}, 400)
                return
            if session_raw and not re.fullmatch(r"[A-Fa-f0-9\-]{8,64}", session_raw):
                self._send_json({"error": "Invalid sessionId"}, 400)
                return
            if agent_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", agent_raw):
                self._send_json({"error": "Invalid agent name"}, 400)
                return

            try:
                metadata = copilot_runner.start_run(
                    project_root,
                    prompt,
                    requested_by=self._authorized_user() or "",
                    model=model_raw or None,
                    session_id=session_raw or None,
                    agent=agent_raw or None,
                )
            except copilot_runner.CopilotRunError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Copilot run start failed for %s", slug)
                self._send_json({"error": f"Failed to start run: {exc}"}, 500)
                return

            self._send_json({"ok": True, "run": metadata}, 202)
            return

        self._send_json({"error": "Invalid copilot path"}, 400)

    # --- Repo-root Copilot CLI handlers ------------------------------------

    def _handle_copilot_root_get(self, request_path: str):
        """Route GET /api/copilot-runtime, /api/copilot-agents, /api/copilot-runs[...]."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        if request_path == "/api/copilot-runtime":
            info = copilot_runner.runtime_info()
            info["scope"] = "repo"
            info["repoRoot"] = str(FACTORY_REPO_ROOT)
            self._send_json(info)
            return

        if request_path == "/api/copilot-agents":
            try:
                agents = copilot_runner.list_agents(FACTORY_REPO_ROOT)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Copilot agent discovery failed")
                self._send_json({"error": f"Failed to list agents: {exc}"}, 500)
                return
            self._send_json({"agents": agents})
            return

        parts = request_path.split("/")
        # ['', 'api', 'copilot-runs', ...]
        if len(parts) >= 3 and parts[2] == "copilot-runs":
            if len(parts) == 3:
                runs = copilot_runner.list_runs(FACTORY_REPO_ROOT)
                self._send_json({"scope": "repo", "runs": runs})
                return
            run_id = parts[3]
            if len(parts) == 4:
                run = copilot_runner.get_run(FACTORY_REPO_ROOT, run_id)
                if run is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(run)
                return
            if len(parts) == 5 and parts[4] == "log":
                tail = copilot_runner.read_log_tail(FACTORY_REPO_ROOT, run_id)
                if tail is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                body = tail.encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if len(parts) == 5 and parts[4] == "diff":
                diff = copilot_runner.diff_run(FACTORY_REPO_ROOT, run_id)
                if diff is None:
                    self._send_json({"error": "Run not found"}, 404)
                    return
                self._send_json(diff)
                return

        self._send_json({"error": "Invalid copilot path"}, 400)

    def _handle_copilot_root_post(self, path: str):
        """Route POST /api/copilot-runs[/<id>/cancel] — repo-root scope."""
        if copilot_runner is None:
            self._send_json({"error": "Copilot CLI runner is not available on this build."}, 503)
            return

        parts = path.split("/")
        # Cancel: /api/copilot-runs/<runId>/cancel
        if len(parts) == 5 and parts[2] == "copilot-runs" and parts[4] == "cancel":
            run_id = parts[3]
            result = copilot_runner.cancel_run(FACTORY_REPO_ROOT, run_id)
            if result is None:
                self._send_json({"error": "Run not found"}, 404)
                return
            self._send_json({"ok": True, "run": result})
            return

        # Start: /api/copilot-runs
        if len(parts) == 3 and parts[2] == "copilot-runs":
            content_length = self._safe_content_length()
            if content_length is None:
                return
            try:
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body) if body else {}
            except Exception as exc:
                self._send_json({"error": f"Invalid request: {exc}"}, 400)
                return

            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self._send_json({"error": "prompt is required"}, 400)
                return

            model_raw = str(payload.get("model", "") or "").strip()
            session_raw = str(payload.get("sessionId", "") or "").strip()
            agent_raw = str(payload.get("agent", "") or "").strip()
            if model_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", model_raw):
                self._send_json({"error": "Invalid model name"}, 400)
                return
            if session_raw and not re.fullmatch(r"[A-Fa-f0-9\-]{8,64}", session_raw):
                self._send_json({"error": "Invalid sessionId"}, 400)
                return
            if agent_raw and not re.fullmatch(r"[A-Za-z0-9._\-]{1,64}", agent_raw):
                self._send_json({"error": "Invalid agent name"}, 400)
                return

            try:
                metadata = copilot_runner.start_run(
                    FACTORY_REPO_ROOT,
                    prompt,
                    requested_by=self._authorized_user() or "",
                    model=model_raw or None,
                    session_id=session_raw or None,
                    agent=agent_raw or None,
                )
            except copilot_runner.CopilotRunError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Repo-root Copilot run start failed")
                self._send_json({"error": f"Failed to start run: {exc}"}, 500)
                return

            self._send_json({"ok": True, "run": metadata}, 202)
            return

        self._send_json({"error": "Invalid copilot path"}, 400)

    def _handle_project_owners_list(self, query: str):
        """GET /api/admin/project-owners[?slug=...] — list owners.

        Returns {"admins": [...], "projects": {slug: [users]}} when slug is
        omitted, or {"slug": ..., "owners": [users]} when a slug is provided.
        """
        params = parse_qs(query or "")
        slug = (params.get("slug", [""])[0] or "").strip()
        owners = _load_owners()
        if slug:
            if not _is_slug_visible(slug):
                self._send_json({"error": "Unknown project"}, 404)
                return
            project_owners = sorted(_project_owners(slug))
            self._send_json({"slug": slug, "owners": project_owners})
            return
        projects = owners.get("projects") or {}
        normalized = {
            s: sorted({str(x).strip().lower() for x in (v if isinstance(v, list) else [v]) if str(x).strip()})
            for s, v in projects.items()
        }
        self._send_json({
            "admins": sorted({str(a).strip().lower() for a in (owners.get("admins") or []) if str(a).strip()}),
            "projects": normalized,
            "readOnly": bool(_OWNERS_JSON_ENV),
        })

    def _handle_project_owners_update(self):
        """POST /api/admin/project-owners — add/remove/set users for a project.

        Body: {"slug": "...", "users": ["a@b.com", ...], "action": "add"|"remove"|"set"}
        Default action is "add". Emails are case-insensitive and de-duplicated.
        """
        if _OWNERS_JSON_ENV:
            self._send_json({
                "error": "Owners are read-only: FACTORY_PORTAL_OWNERS_JSON is set. "
                         "Update the secret and restart the portal."
            }, 409)
            return

        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception as exc:
            self._send_json({"error": f"Invalid request: {exc}"}, 400)
            return

        slug = str(payload.get("slug", "")).strip()
        action = str(payload.get("action", "add")).strip().lower() or "add"
        raw_users = payload.get("users")
        if raw_users is None and "user" in payload:
            raw_users = [payload.get("user")]
        if isinstance(raw_users, str):
            raw_users = [raw_users]
        if not isinstance(raw_users, list):
            raw_users = []
        users = []
        for u in raw_users:
            if not isinstance(u, str):
                continue
            u_norm = u.strip().lower()
            if u_norm and u_norm not in users:
                users.append(u_norm)

        if not slug:
            self._send_json({"error": "slug is required"}, 400)
            return
        if action not in {"add", "remove", "set"}:
            self._send_json({"error": "action must be add, remove, or set"}, 400)
            return
        if action in {"add", "remove"} and not users:
            self._send_json({"error": "users list cannot be empty for add/remove"}, 400)
            return
        if not _is_slug_visible(slug):
            self._send_json({"error": "Unknown project slug"}, 404)
            return

        data = _load_owners()
        if not isinstance(data.get("projects"), dict):
            data["projects"] = {}
        current_raw = data["projects"].get(slug) or []
        if isinstance(current_raw, str):
            current_raw = [current_raw]
        current = []
        for u in current_raw:
            if not isinstance(u, str):
                continue
            u_norm = u.strip().lower()
            if u_norm and u_norm not in current:
                current.append(u_norm)

        if action == "add":
            for u in users:
                if u not in current:
                    current.append(u)
        elif action == "remove":
            current = [u for u in current if u not in set(users)]
        else:  # set
            current = list(users)

        data["projects"][slug] = sorted(current)
        _save_owners(data)

        # Mirror to blob so other replicas / restarts pick it up.
        try:
            blob_sync.upload_owners(OWNERS_FILE)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Owners blob upload failed: %s", exc)

        self._send_json({
            "slug": slug,
            "action": action,
            "owners": sorted(current),
        }, 200)

    def _call_csa_companion(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        if not CSA_COPILOT_API_BASE:
            return 503, {"error": "CSA companion service is not configured."}

        url = f"{CSA_COPILOT_API_BASE}{path}"
        headers = {"Content-Type": "application/json"}
        if CSA_COPILOT_API_KEY:
            headers["x-api-key"] = CSA_COPILOT_API_KEY
        request_id = self.headers.get("x-request-id", str(uuid.uuid4()))
        headers["x-request-id"] = request_id

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        try:
            req = Request(url=url, data=data, method=method, headers=headers)
            with urlopen(req, timeout=CSA_COPILOT_TIMEOUT_SECONDS) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body)
        except URLError as exc:
            logger.warning("CSA companion request failed: %s %s (%s)", method, url, exc)
            return 502, {"error": "Failed to reach CSA companion service."}
        except json.JSONDecodeError:
            return 502, {"error": "CSA companion returned invalid JSON."}

    def _handle_csa_copilot_tools(self):
        status_code, payload = self._call_csa_companion("GET", "/api/copilot/tools")
        self._send_json(payload, status_code)

    def _handle_csa_copilot_ask(self):
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        question = str(payload.get("question", "")).strip()
        context = str(payload.get("context", "")).strip()
        session_id = str(payload.get("session_id", "")).strip()
        user_id = str(payload.get("user_id", "portal-user")).strip() or "portal-user"

        if len(question) < 3:
            self._send_json({"error": "question must be at least 3 characters"}, 400)
            return

        upstream_payload = {
            "question": question,
            "context": context,
            "session_id": session_id,
            "user_id": user_id,
        }
        status_code, response_payload = self._call_csa_companion("POST", "/api/copilot/ask", upstream_payload)
        self._send_json(response_payload, status_code)

    # ---------------------------------------------------------------------
    # BRD Copilot (Phase 1 prototype) — grounded chat that drafts BRDs
    # ---------------------------------------------------------------------
    _BRD_CHAT_SYSTEM_PROMPT = (
        "You are BRD Copilot, an assistant embedded in the Azure Architecture Factory (AAF) portal. "
        "Your job is to help a user author a Business Requirements Document (BRD) that AAF can turn "
        "into an Azure architecture, service code, and infrastructure-as-code.\n\n"
        "AAF CAPABILITIES:\n"
        "- Languages: Python 3.11 / FastAPI  OR  .NET 8 / ASP.NET Core Minimal APIs (accepts C# aliases).\n"
        "- Infrastructure-as-Code: Bicep (Azure-native) OR Terraform (azurerm ~> 4.14).\n"
        "- Network tiers: public (default) | vnet-integrated | private.\n"
        "- Archetypes (auto-detected from BRD content): extraction-chat (LLM extraction/chat over "
        "customer documents), rag-qa (retrieval-augmented Q&A), api-service (generic backend).\n"
        "- Optional toggles: generateInfra, runSecurityAudit, enableObservability.\n\n"
        "GOOD BRD STRUCTURE:\n"
        "# Project: <name>\n"
        "## Business Goal\n## Key Requirements\n## Success Criteria\n## Out of Scope\n"
        "## Timeline\n"
        "Optional hint lines the factory understands:\n"
        "  Implementation language: python | dotnet | csharp\n"
        "  Infrastructure as code: bicep | terraform\n"
        "  Network tier: public | vnet-integrated | private\n\n"
        "INTERACTION RULES:\n"
        "1. Ask clarifying questions only when the request is genuinely ambiguous. Otherwise draft.\n"
        "2. Prefer concrete, narrow scope. Do not invent requirements the user did not imply.\n"
        "3. When you have enough to draft, return a BRD in `brd_draft`. You can revise on follow-ups.\n"
        "4. Suggest language/IaC/network based on the workload: "
        "Python for AI/ML and RAG; .NET for heavy throughput enterprise APIs; "
        "Terraform when the user mentions multi-cloud or existing Terraform estate; "
        "vnet-integrated or private when they mention regulated data, HIPAA, PCI, or on-prem integration.\n"
        "5. Slugify project name to kebab-case for `suggested_slug` (lowercase, alphanumeric + hyphens).\n\n"
        "REVIEW MODE — triggered when the user pastes an existing BRD and asks for evaluation, "
        "readiness, gaps, or missing information:\n"
        "  a. Score the BRD against this readiness rubric (1 point per item, max 10):\n"
        "     [1] Clear business goal in one sentence\n"
        "     [2] Named primary users / personas and their job-to-be-done\n"
        "     [3] Concrete key requirements (verbs + nouns, not aspirations)\n"
        "     [4] Measurable success criteria (numbers, SLOs, adoption targets)\n"
        "     [5] Explicit out-of-scope section (what we are NOT building)\n"
        "     [6] Data sources and data sensitivity identified (PII / PHI / PCI / public)\n"
        "     [7] Integration points with existing systems listed\n"
        "     [8] Non-functional requirements (performance, availability, security, compliance)\n"
        "     [9] Timeline or milestone expectations\n"
        "     [10] Factory hints stated or inferable (language, IaC, network tier)\n"
        "  b. In `reply`, output a markdown scorecard: total score, per-item ✅/⚠️/❌ with a "
        "one-line justification, then a 'Missing information' section listing targeted "
        "questions the user should answer. Ask those questions directly — do not hedge.\n"
        "  c. In `brd_draft`, return an IMPROVED version of the BRD that fills safe gaps "
        "(structure, section headers, normalized hints) and flags the user-answerable gaps "
        "with `TODO:` markers inline so the user can complete them. Do NOT fabricate domain "
        "facts (users, SLAs, data sources) — use `TODO:` instead.\n"
        "  d. If the user follows up with answers, revise `brd_draft` by replacing the "
        "corresponding TODOs. Re-score and show the delta.\n\n"
        "RESPONSE FORMAT: You MUST respond with a single JSON object with these keys:\n"
        '  "reply": string — your chat message to the user (concise, markdown allowed).\n'
        '  "brd_draft": string | null — full BRD markdown ready to paste, or null if not yet drafting.\n'
        '  "suggested_slug": string | null — kebab-case project slug, or null.\n'
        '  "suggested_options": object | null — any of: implementation_language ("python"|"dotnet"|"csharp"), '
        'iac_tool ("bicep"|"terraform"), network_tier ("public"|"vnet-integrated"|"private"). Omit keys you cannot justify.\n'
        "No prose outside the JSON object.\n\n"
        "SELF-AWARENESS: You are **BRD Copilot**, focused on authoring and reviewing BRDs. A separate "
        "copilot, **Project Copilot** (🛠️ per-project, bottom-right), is tool-enabled and answers "
        "questions about an already-generated project (architecture, cost, observability, deploy commands). "
        "You do NOT have tools; you do NOT read project files. If the user asks about an existing project's "
        "cost, observability, or deployment, tell them to use Project Copilot from that project's card. "
        "Full reference: `docs/COPILOT_GUIDE.md`."
    )

    def _handle_brd_chat(self):
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        raw_messages = payload.get("messages", [])
        if not isinstance(raw_messages, list) or not raw_messages:
            self._send_json({"error": "messages must be a non-empty list"}, 400)
            return

        # Sanitize: keep only {role, content} strings, cap length/count.
        cleaned: list[dict] = []
        for m in raw_messages[-20:]:  # last 20 turns max
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", "")).strip().lower()
            content = str(m.get("content", "")).strip()
            if role not in ("user", "assistant") or not content:
                continue
            cleaned.append({"role": role, "content": content[:4000]})

        if not cleaned:
            self._send_json({"error": "messages must contain at least one user turn"}, 400)
            return

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
        auth = _aoai_auth_header()

        # Graceful fallback when Azure OpenAI is not configured — prototype still visible.
        if not (endpoint and deployment and auth):
            self._send_json(
                {
                    "reply": (
                        "**BRD Copilot is not configured on this portal.**\n\n"
                        "To enable it, set these environment variables on the portal server and restart:\n\n"
                        "- `AZURE_OPENAI_ENDPOINT`\n"
                        "- `AZURE_OPENAI_DEPLOYMENT` (e.g., `gpt-4o`, `gpt-4o-mini`)\n"
                        "- `AZURE_OPENAI_API_KEY`\n\n"
                        "Until then, you can still author BRDs manually in the form above. The portal "
                        "dropdowns (language, IaC tool, network tier) already let you override anything "
                        "the factory would auto-detect."
                    ),
                    "brd_draft": None,
                    "suggested_slug": None,
                    "suggested_options": None,
                    "stub_mode": True,
                },
                200,
            )
            return

        chat_messages = [{"role": "system", "content": self._BRD_CHAT_SYSTEM_PROMPT}] + cleaned

        request_body = json.dumps(
            {
                "messages": chat_messages,
                "temperature": 0.3,
                "max_tokens": 1800,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        req = Request(url, data=request_body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header(auth[0], auth[1])

        try:
            with urlopen(req, timeout=45) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
        except URLError as e:
            logging.warning("BRD chat upstream error: %s", e)
            self._send_json({"error": f"Azure OpenAI call failed: {e}"}, 502)
            return
        except Exception as e:
            logging.warning("BRD chat unexpected error: %s", e)
            self._send_json({"error": f"Azure OpenAI call failed: {e}"}, 502)
            return

        try:
            raw_content = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_content)
        except Exception as e:
            logging.warning("BRD chat response parse error: %s; raw=%r", e, data)
            self._send_json(
                {
                    "reply": (
                        "I couldn't parse a structured reply this time. Could you rephrase? "
                        "(The model returned free text instead of JSON.)"
                    ),
                    "brd_draft": None,
                    "suggested_slug": None,
                    "suggested_options": None,
                },
                200,
            )
            return

        # Narrow response to the documented contract; drop anything unexpected.
        reply = str(parsed.get("reply", "")).strip() or "(no reply)"
        brd_draft = parsed.get("brd_draft")
        if brd_draft is not None and not isinstance(brd_draft, str):
            brd_draft = None
        suggested_slug = parsed.get("suggested_slug")
        if suggested_slug is not None and not isinstance(suggested_slug, str):
            suggested_slug = None
        opts = parsed.get("suggested_options")
        clean_opts: dict = {}
        if isinstance(opts, dict):
            il = _sanitize_implementation_language(opts.get("implementation_language"))
            if il:
                clean_opts["implementation_language"] = il
            iac = opts.get("iac_tool")
            if iac in ("bicep", "terraform"):
                clean_opts["iac_tool"] = iac
            nt = opts.get("network_tier")
            if nt in ("public", "vnet-integrated", "private"):
                clean_opts["network_tier"] = nt

        self._send_json(
            {
                "reply": reply,
                "brd_draft": brd_draft,
                "suggested_slug": suggested_slug,
                "suggested_options": clean_opts or None,
            },
            200,
        )

    # ---------------------------------------------------------------------
    # Per-project Copilot (Phase 2 prototype)
    # - Architecture Q&A  - Cost evaluation  - Operations  - Observability
    # ---------------------------------------------------------------------
    _PROJECT_CHAT_SYSTEM_PROMPT = (
        "You are Project Copilot, embedded in the Azure Architecture Factory (AAF) portal. "
        "You answer questions about ONE specific generated project. You have access to a "
        "READ-ONLY context bundle (project-manifest.json excerpts, doc excerpts, infra "
        "excerpts) injected below by the server. You are an expert on:\n"
        "  1. Architecture & code — what services exist, how they connect, which archetype was used.\n"
        "  2. Cost evaluation — estimate monthly Azure spend from the infra resources and offer "
        "concrete cost-reduction moves (tier downgrade, autoscale, reserved capacity, serverless).\n"
        "  3. Operations — deployment, rollout strategy, rollback, incident response, health probes, "
        "scaling, backup/restore, disaster recovery.\n"
        "  4. Observability — Application Insights wiring, Log Analytics, KQL queries, alert rules, "
        "dashboards, SLOs/SLIs, distributed tracing.\n\n"
        "RULES:\n"
        "- Ground every answer in the provided CONTEXT. If the context does not contain the answer, "
        "say so plainly and suggest what file the user should look at.\n"
        "- When asked about cost, always list assumptions (region, traffic, retention) and give a "
        "rough monthly USD range per resource. Prefer Azure list prices (East US 2) unless the "
        "manifest says otherwise.\n"
        "- Never invent file paths, resource names, or SKUs that are not in the context.\n"
        "- Keep responses under ~500 words unless the user explicitly asks for more depth.\n"
        "- Use concise markdown: short paragraphs, bullet lists, tables for cost/ops summaries.\n"
        "- When suggesting changes, reference the exact file path the user would edit "
        "(e.g., `infra/modules/compute/containerapp.bicep`)."
    )

    # Per-project file budget — keep total prompt bounded.
    _PROJECT_CHAT_MAX_CONTEXT_CHARS = 18_000
    _PROJECT_CHAT_DOC_FILES = (
        "docs/architecture-overview.md",
        "docs/detailed-architecture.md",
        "docs/production-readiness.md",
        "docs/governance-model.md",
        "docs/traceability-matrix.md",
        "docs/delivery-milestones.md",
        "docs/success-criteria.md",
        "README.md",
        "DEPLOY.md",
    )
    _PROJECT_CHAT_INFRA_GLOBS = ("main.bicep", "main.tf", "main.bicepparam")

    def _build_project_chat_context(self, project_root: pathlib.Path) -> str:
        """Read a bounded bundle of project files and format as a system context block."""
        budget = self._PROJECT_CHAT_MAX_CONTEXT_CHARS
        chunks: list[str] = []

        def _add(label: str, body: str) -> None:
            nonlocal budget
            if budget <= 0 or not body:
                return
            body = body.strip()
            if len(body) > budget:
                body = body[: max(0, budget - 40)] + "\n…[truncated]"
            chunk = f"### {label}\n\n{body}\n"
            chunks.append(chunk)
            budget -= len(chunk)

        # 1. Manifest (compact — drop verbose prose fields).
        manifest_path = project_root / "project-manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                compact = {
                    "project": manifest.get("project"),
                    "title": manifest.get("title"),
                    "status": manifest.get("status"),
                    "capabilities": manifest.get("capabilities"),
                    "generation_options": manifest.get("generation_options"),
                    "analysis": manifest.get("analysis"),
                    "implementation_language": manifest.get("implementation_language"),
                    "iac_tool": manifest.get("iac_tool"),
                    "services": manifest.get("services"),
                    "architecture": manifest.get("architecture"),
                }
                compact = {k: v for k, v in compact.items() if v is not None}
                _add("project-manifest.json (compact)", json.dumps(compact, indent=2))
            except Exception:
                pass

        # 2. Doc excerpts.
        for rel in self._PROJECT_CHAT_DOC_FILES:
            if budget <= 0:
                break
            path = project_root / rel
            if path.is_file():
                try:
                    _add(rel, path.read_text(encoding="utf-8"))
                except Exception:
                    continue

        # 3. Infra — scan infra/ for the known roots.
        infra_dir = project_root / "infra"
        if infra_dir.is_dir() and budget > 0:
            for name in self._PROJECT_CHAT_INFRA_GLOBS:
                if budget <= 0:
                    break
                for infra_path in sorted(infra_dir.rglob(name)):
                    if budget <= 0:
                        break
                    try:
                        rel = infra_path.relative_to(project_root).as_posix()
                        _add(rel, infra_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue

        # 4. Dir listing (so the model can point the user at files it didn't ingest).
        if budget > 0:
            try:
                listing: list[str] = []
                for entry in sorted(project_root.rglob("*")):
                    if entry.is_dir():
                        continue
                    rel = entry.relative_to(project_root).as_posix()
                    # Skip heavyweight dirs we would never cite.
                    if rel.startswith(("logs/", ".git/", "node_modules/", "__pycache__/")):
                        continue
                    listing.append(rel)
                    if len(listing) >= 200:
                        break
                _add("file-tree (paths only, up to 200)", "\n".join(listing))
            except Exception:
                pass

        return "\n".join(chunks) if chunks else "(no project context available)"

    # ---------------------------------------------------------------------
    # Phase 3: Tool-calling for Project Copilot
    # All tools are READ-ONLY. No deploys. No writes. Paths are clamped
    # to the project root to prevent directory traversal.
    # ---------------------------------------------------------------------
    _PROJECT_CHAT_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "describe_my_capabilities",
                "description": (
                    "Return a machine-readable description of THIS copilot: who it is, what tools "
                    "it has, what it will not do, and pointers to the user-facing guide. Call this "
                    "whenever the user asks what you can do, what tools you have, how you work, "
                    "or what your limits are. The return value is authoritative — do not paraphrase "
                    "from memory, summarize the fields."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_project_file",
                "description": (
                    "Read the contents of a single file inside the current project. "
                    "Use this to inspect a file not included in the initial context "
                    "bundle. Returns up to 20 KB of text."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path inside the project, e.g. 'infra/modules/compute/containerapp.bicep' or 'src/main.py'.",
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_project_files",
                "description": (
                    "List files in the project matching a glob relative to the project root. "
                    "Returns up to 200 paths. Use this to discover files before calling read_project_file."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "glob": {
                            "type": "string",
                            "description": "Glob pattern, e.g. 'infra/**/*.bicep', 'src/**/*.py', 'docs/*.md'.",
                        }
                    },
                    "required": ["glob"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scan_cost_resources",
                "description": (
                    "Scan the project's infra files (Bicep and Terraform) and return a structured list "
                    "of billable Azure resources with their SKUs, kinds, and the file they were declared in. "
                    "Use this as the factual basis for cost estimation. Never invent resources not in the output."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scan_observability",
                "description": (
                    "Deterministic scan of infra + code for observability signals: Application Insights, "
                    "Log Analytics workspace, health probe endpoints, structured logging, alert rules, "
                    "OpenTelemetry wiring. Returns a checklist with present / missing items."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "prepare_deploy_commands",
                "description": (
                    "Return the copy-paste Azure CLI / azd commands to deploy this project, based on the "
                    "detected IaC tool (Bicep or Terraform). Does NOT execute anything. The user runs the "
                    "commands themselves in a terminal."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resource_group": {
                            "type": "string",
                            "description": "Target Azure resource group name. If unknown, pass 'rg-<slug>'.",
                        },
                        "location": {
                            "type": "string",
                            "description": "Azure region, e.g. 'eastus2'. Defaults to 'eastus2' if omitted.",
                        },
                    },
                    "required": [],
                },
            },
        },
    ]

    _PROJECT_CHAT_TOOL_MAX_FILE_BYTES = 20_000
    _PROJECT_CHAT_TOOL_MAX_ITERATIONS = 5

    def _tool_describe_my_capabilities(self, project_root: pathlib.Path, args: dict) -> str:
        return json.dumps({
            "name": "Project Copilot",
            "icon": "🛠️",
            "scope": "one specific factory-generated project",
            "grounding": "18 KB context bundle per turn (manifest + docs/*.md + infra/**/*.bicep|tf|bicepparam + src/ tests/ file tree)",
            "tool_calling": {
                "enabled": True,
                "max_iterations_per_turn": self._PROJECT_CHAT_TOOL_MAX_ITERATIONS,
                "tools": [
                    {"name": "describe_my_capabilities", "purpose": "self-introspection"},
                    {"name": "read_project_file", "purpose": "read a file (up to 20 KB), path clamped to project root"},
                    {"name": "list_project_files", "purpose": "glob the project tree (up to 200 paths)"},
                    {"name": "scan_cost_resources", "purpose": "deterministic infra scan returning billable resources + heuristic $/month"},
                    {"name": "scan_observability", "purpose": "deterministic 7-point observability checklist"},
                    {"name": "prepare_deploy_commands", "purpose": "return copy-paste az/azd/terraform CLI; does NOT execute"},
                ],
            },
            "safety": {
                "read_only": True,
                "path_traversal_blocked": True,
                "no_writes": True,
                "no_shell_execution": True,
                "no_azure_api_calls": True,
                "no_cross_project_access": True,
                "max_file_read_bytes": self._PROJECT_CHAT_TOOL_MAX_FILE_BYTES,
                "max_list_results": 200,
            },
            "cannot_do": [
                "Edit BRD, infra, or source code",
                "Run terraform apply, az deployment, azd up, or any shell command",
                "Call live Azure APIs, GitHub APIs, or any external HTTP",
                "Access files in other projects",
                "Persist conversation history (session only, cleared on refresh)",
            ],
            "sibling_copilot": {
                "name": "BRD Copilot",
                "scope": "BRD authoring + review",
                "how_to_reach": "bottom-left 💬 button on the portal (a separate copilot, not me)",
            },
            "user_guide": "/docs/COPILOT_GUIDE.md",
            "footer_shown_when_tools_used": "🛠️ Used: <tool_names>",
        })

    def _tool_read_project_file(self, project_root: pathlib.Path, args: dict) -> str:
        rel = str(args.get("path", "")).strip().lstrip("/\\")
        if not rel or ".." in rel.split("/") or ".." in rel.split("\\"):
            return json.dumps({"error": "invalid path"})
        target = (project_root / rel).resolve()
        if project_root.resolve() not in target.parents and target != project_root.resolve():
            return json.dumps({"error": "path escapes project root"})
        if not target.exists() or not target.is_file():
            return json.dumps({"error": f"file not found: {rel}"})
        try:
            data = target.read_bytes()
        except Exception as e:
            return json.dumps({"error": f"read failed: {e}"})
        truncated = False
        if len(data) > self._PROJECT_CHAT_TOOL_MAX_FILE_BYTES:
            data = data[: self._PROJECT_CHAT_TOOL_MAX_FILE_BYTES]
            truncated = True
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return json.dumps({"path": rel, "truncated": truncated, "content": text})

    def _tool_list_project_files(self, project_root: pathlib.Path, args: dict) -> str:
        glob = str(args.get("glob", "")).strip().lstrip("/\\")
        if not glob or ".." in glob:
            return json.dumps({"error": "invalid glob"})
        try:
            matches: list[str] = []
            for p in project_root.glob(glob):
                if p.is_file():
                    rel = p.relative_to(project_root).as_posix()
                    matches.append(rel)
                    if len(matches) >= 200:
                        break
            return json.dumps({"glob": glob, "count": len(matches), "paths": matches})
        except Exception as e:
            return json.dumps({"error": f"glob failed: {e}"})

    # Heuristic resource-cost table — rough list prices in USD/month, eastus2.
    # These are deliberately approximate; the chat model is instructed to show
    # assumptions and cite this as "heuristic, verify with Azure Pricing Calc".
    _COST_HEURISTICS_USD_MONTH = {
        "Microsoft.App/containerApps": (15, 120),
        "Microsoft.Web/sites": (13, 200),
        "Microsoft.Web/serverfarms": (13, 300),
        "Microsoft.DocumentDB/databaseAccounts": (25, 300),
        "Microsoft.Storage/storageAccounts": (2, 40),
        "Microsoft.KeyVault/vaults": (0, 5),
        "Microsoft.CognitiveServices/accounts": (20, 500),
        "Microsoft.Insights/components": (0, 50),
        "Microsoft.OperationalInsights/workspaces": (0, 80),
        "Microsoft.ContainerRegistry/registries": (5, 50),
        "Microsoft.ServiceBus/namespaces": (10, 100),
        "Microsoft.EventHub/namespaces": (10, 150),
        "Microsoft.Sql/servers": (0, 0),
        "Microsoft.Sql/servers/databases": (5, 200),
        "Microsoft.Cache/Redis": (17, 200),
        "Microsoft.ApiManagement/service": (150, 2700),
        "Microsoft.Network/virtualNetworks": (0, 0),
        "Microsoft.Network/networkSecurityGroups": (0, 0),
        "Microsoft.Network/privateEndpoints": (8, 12),
        "Microsoft.Search/searchServices": (75, 1000),
    }

    def _tool_scan_cost_resources(self, project_root: pathlib.Path, args: dict) -> str:
        infra = project_root / "infra"
        if not infra.is_dir():
            return json.dumps({"resources": [], "note": "No infra/ directory found."})

        resources: list[dict] = []
        # Bicep: match `resource <symbol> 'Microsoft.Foo/bar@<api>' = {`
        bicep_re = re.compile(
            r"resource\s+(\w+)\s+'([A-Za-z0-9.]+/[A-Za-z0-9/]+)@[^']+'\s*=",
        )
        # Terraform: match `resource "azurerm_<type>" "<name>"`
        tf_re = re.compile(r'resource\s+"(azurerm_[a-z0-9_]+)"\s+"([A-Za-z0-9_-]+)"')
        # Try to pull SKU / tier hints if nearby.
        sku_re = re.compile(r"(?i)\b(?:sku|tier|kind)\s*[:=]\s*['\"]?([A-Za-z0-9_.-]+)")

        for path in sorted(infra.rglob("*")):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not (name.endswith(".bicep") or name.endswith(".tf")):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = path.relative_to(project_root).as_posix()
            if name.endswith(".bicep"):
                for m in bicep_re.finditer(text):
                    symbol, rtype = m.group(1), m.group(2)
                    # Look ahead 400 chars for SKU/tier/kind
                    window = text[m.end(): m.end() + 400]
                    sku_match = sku_re.search(window)
                    low, high = self._COST_HEURISTICS_USD_MONTH.get(rtype, (0, 0))
                    resources.append({
                        "symbol": symbol,
                        "type": rtype,
                        "file": rel,
                        "sku_hint": sku_match.group(1) if sku_match else None,
                        "monthly_usd_low": low,
                        "monthly_usd_high": high,
                    })
            else:
                for m in tf_re.finditer(text):
                    tf_type, tf_name = m.group(1), m.group(2)
                    resources.append({
                        "symbol": tf_name,
                        "type": tf_type,
                        "file": rel,
                        "sku_hint": None,
                        "monthly_usd_low": 0,  # TF list would need a separate mapping
                        "monthly_usd_high": 0,
                    })

        total_low = sum(r["monthly_usd_low"] for r in resources)
        total_high = sum(r["monthly_usd_high"] for r in resources)
        return json.dumps({
            "resources": resources,
            "count": len(resources),
            "monthly_total_usd_low": total_low,
            "monthly_total_usd_high": total_high,
            "assumptions": [
                "Region: East US 2",
                "Consumption / Standard SKUs where not specified",
                "Low traffic (under 1M requests/mo, <10 GB egress)",
                "Log retention: 30 days",
                "Figures are heuristic. Verify with Azure Pricing Calculator before committing to budget.",
            ],
        })

    def _tool_scan_observability(self, project_root: pathlib.Path, args: dict) -> str:
        signals = {
            "application_insights": False,
            "log_analytics_workspace": False,
            "health_probe_endpoint": False,
            "structured_logging": False,
            "alert_rules": False,
            "opentelemetry": False,
            "diagnostic_settings": False,
        }
        evidence: dict[str, list[str]] = {k: [] for k in signals}

        # Scan infra
        infra = project_root / "infra"
        if infra.is_dir():
            for path in infra.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in (".bicep", ".tf", ".bicepparam"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                rel = path.relative_to(project_root).as_posix()
                lower = text.lower()
                if "microsoft.insights/components" in lower or "azurerm_application_insights" in lower:
                    signals["application_insights"] = True
                    evidence["application_insights"].append(rel)
                if "microsoft.operationalinsights/workspaces" in lower or "azurerm_log_analytics_workspace" in lower:
                    signals["log_analytics_workspace"] = True
                    evidence["log_analytics_workspace"].append(rel)
                if "microsoft.insights/metricalerts" in lower or "azurerm_monitor_metric_alert" in lower or "microsoft.insights/scheduledqueryrules" in lower:
                    signals["alert_rules"] = True
                    evidence["alert_rules"].append(rel)
                if "microsoft.insights/diagnosticsettings" in lower or "azurerm_monitor_diagnostic_setting" in lower:
                    signals["diagnostic_settings"] = True
                    evidence["diagnostic_settings"].append(rel)

        # Scan code for health probe + OTel + structured logging hints
        src = project_root / "src"
        if src.is_dir():
            for path in src.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in (".py", ".cs", ".ts", ".js"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                rel = path.relative_to(project_root).as_posix()
                lower = text.lower()
                if "/health" in lower or "/healthz" in lower or "healthcheck" in lower or "addhealthchecks" in lower:
                    signals["health_probe_endpoint"] = True
                    evidence["health_probe_endpoint"].append(rel)
                if "opentelemetry" in lower or "otlp" in lower or "addopentelemetry" in lower:
                    signals["opentelemetry"] = True
                    evidence["opentelemetry"].append(rel)
                if "ilogger<" in lower or "structlog" in lower or "logging.getlogger" in lower or "applicationinsights" in lower:
                    signals["structured_logging"] = True
                    evidence["structured_logging"].append(rel)

        # Cap evidence lists to 5 entries each for brevity.
        for k in evidence:
            evidence[k] = evidence[k][:5]

        return json.dumps({
            "signals": signals,
            "evidence": evidence,
            "score": f"{sum(1 for v in signals.values() if v)}/{len(signals)}",
        })

    def _tool_prepare_deploy_commands(self, project_root: pathlib.Path, slug: str, args: dict) -> str:
        rg = str(args.get("resource_group", "")).strip() or f"rg-{slug}"
        loc = str(args.get("location", "")).strip() or "eastus2"

        infra = project_root / "infra"
        has_bicep = infra.is_dir() and any(infra.rglob("main.bicep"))
        has_tf = infra.is_dir() and any(infra.rglob("main.tf"))
        has_azure_yaml = (project_root / "azure.yaml").is_file()

        # Detect ACA Express mode from project manifest
        manifest_path = project_root / "project-manifest.json"
        aca_express = False
        aca_express_region = "westcentralus"
        aca_express_image = ""
        if manifest_path.is_file():
            try:
                with manifest_path.open(encoding="utf-8") as f:
                    manifest = json.load(f)
                gen_opts = manifest.get("generationOptions") or manifest.get("generation_options") or {}
                if gen_opts.get("deploymentMode") == "aca-express":
                    aca_express = True
                    aca_express_region = gen_opts.get("acaExpressRegion", "westcentralus")
                    aca_express_image = str(gen_opts.get("acaExpressImage") or "").strip()
            except Exception:
                pass

        blocks: list[dict] = []

        if aca_express:
            env_name = f"aca-express-env-{slug}"
            app_name = slug
            image_cmd = aca_express_image or "<your-container-image>  # e.g. mcr.microsoft.com/azuredocs/aca-helloworld:latest"
            blocks.append({
                "tool": "az containerapp",
                "title": "⚡ Deploy with ACA Express (preview)",
                "commands": [
                    "az login",
                    f"az group create --name {rg} --location {aca_express_region}",
                    f"az containerapp env create --name {env_name} --resource-group {rg} --location {aca_express_region} --environment-mode express",
                    f"az containerapp up --name {app_name} --resource-group {rg} --environment {env_name} --image {image_cmd} --ingress external --target-port 80",
                    f"# Management portal: https://containerapps.azure.com/",
                    f"az containerapp show --name {app_name} --resource-group {rg} --query properties.configuration.ingress.fqdn --output tsv",
                ],
                "note": "ACA Express (preview) — HTTP-only workloads, westcentralus / eastasia only. No VNet, Managed Identity, Key Vault, Dapr, or KEDA.",
            })

        if has_azure_yaml:
            blocks.append({
                "tool": "azd",
                "title": "Deploy with Azure Developer CLI",
                "commands": [
                    "azd auth login",
                    f"azd env new {slug} --location {loc}",
                    "azd up",
                ],
            })

        if has_bicep:
            blocks.append({
                "tool": "az bicep",
                "title": "Deploy with Azure CLI + Bicep",
                "commands": [
                    "az login",
                    f"az group create --name {rg} --location {loc}",
                    f"az deployment group create --resource-group {rg} "
                    f"--template-file infra/main.bicep "
                    f"--parameters @infra/params/main.bicepparam",
                ],
            })

        if has_tf:
            blocks.append({
                "tool": "terraform",
                "title": "Deploy with Terraform",
                "commands": [
                    "az login",
                    "cd infra",
                    "terraform init",
                    "terraform validate",
                    f"terraform plan -var=\"resource_group_name={rg}\" -var=\"location={loc}\"",
                    "terraform apply",
                ],
            })

        if not blocks:
            blocks.append({
                "tool": "none",
                "title": "No deployment artifacts detected",
                "commands": [
                    "# This project does not contain infra/ or azure.yaml.",
                    "# Was it generated with generate_infra=false?",
                ],
            })

        return json.dumps({
            "resource_group": rg,
            "location": aca_express_region if aca_express else loc,
            "blocks": blocks,
            "note": "These commands are not executed by the portal — copy-paste into a terminal.",
        })

    def _execute_project_chat_tool(
        self,
        project_root: pathlib.Path,
        slug: str,
        tool_name: str,
        args: dict,
    ) -> str:
        try:
            if tool_name == "describe_my_capabilities":
                return self._tool_describe_my_capabilities(project_root, args)
            if tool_name == "read_project_file":
                return self._tool_read_project_file(project_root, args)
            if tool_name == "list_project_files":
                return self._tool_list_project_files(project_root, args)
            if tool_name == "scan_cost_resources":
                return self._tool_scan_cost_resources(project_root, args)
            if tool_name == "scan_observability":
                return self._tool_scan_observability(project_root, args)
            if tool_name == "prepare_deploy_commands":
                return self._tool_prepare_deploy_commands(project_root, slug, args)
            return json.dumps({"error": f"unknown tool: {tool_name}"})
        except Exception as e:
            logging.warning("Tool %s failed: %s", tool_name, e)
            return json.dumps({"error": f"tool {tool_name} failed: {e}"})

    def _call_aoai_raw(self, messages: list, *, tools: list | None = None,
                       max_tokens: int = 1500, temperature: float = 0.2) -> tuple[int, dict | str]:
        """Low-level AOAI call that returns the raw first-choice message dict (or error string)."""
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
        auth = _aoai_auth_header()

        if not (endpoint and deployment and auth):
            return 200, {
                "role": "assistant",
                "content": (
                    "**Project Copilot is not configured on this portal.**\n\n"
                    "Set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT` on the portal "
                    "server. For auth, either set `AZURE_OPENAI_API_KEY`, or install "
                    "`azure-identity` and sign in with `az login` so the portal can use "
                    "your Entra ID identity (works with `disableLocalAuth=true` accounts)."
                ),
            }

        req_body: dict = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            req_body["tools"] = tools
            req_body["tool_choice"] = "auto"

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        req = Request(url, data=json.dumps(req_body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header(auth[0], auth[1])

        try:
            data = json.loads(_aoai_urlopen(req, timeout=60).decode("utf-8"))
            return 200, data["choices"][0]["message"]
        except URLError as e:
            logging.warning("Azure OpenAI call failed: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"
        except Exception as e:
            logging.warning("Azure OpenAI unexpected error: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"

    def _handle_project_chat(self, slug: str):
        project_root = self._resolve_project_root(slug)
        if not project_root:
            self._send_json({"error": "Project not found"}, 404)
            return

        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        raw_messages = payload.get("messages", [])
        if not isinstance(raw_messages, list) or not raw_messages:
            self._send_json({"error": "messages must be a non-empty list"}, 400)
            return

        cleaned: list[dict] = []
        for m in raw_messages[-20:]:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", "")).strip().lower()
            content = str(m.get("content", "")).strip()
            if role not in ("user", "assistant") or not content:
                continue
            cleaned.append({"role": role, "content": content[:4000]})

        if not cleaned:
            self._send_json({"error": "messages must contain at least one user turn"}, 400)
            return

        context_block = self._build_project_chat_context(project_root)
        system_prompt = (
            f"{self._PROJECT_CHAT_SYSTEM_PROMPT}\n\n"
            f"### CURRENT PROJECT\n\nslug: `{slug}`\n\n"
            f"### CONTEXT\n\n{context_block}\n\n"
            "### TOOLS\n\n"
            "You have read-only tools to explore files, scan cost, audit observability, and prepare "
            "deploy commands. Prefer calling tools over guessing. Use `scan_cost_resources` before "
            "estimating cost, `scan_observability` before answering observability questions, and "
            "`prepare_deploy_commands` for any deployment request. Use `read_project_file` only when "
            "the context bundle does not already contain what you need.\n\n"
            "### SELF-AWARENESS\n\n"
            "You are **Project Copilot**, the tool-enabled per-project assistant. A separate copilot "
            "(**BRD Copilot**, bottom-left of the portal) handles BRD authoring and review — you do not. "
            "When the user asks what you can do, what tools you have, how you work, what you cannot do, "
            "or how you compare to the BRD Copilot, CALL `describe_my_capabilities` and summarize its "
            "return value. Never invent capabilities. The canonical user guide is `docs/COPILOT_GUIDE.md`."
        )

        chat_messages: list = [{"role": "system", "content": system_prompt}] + cleaned

        tools_used: list[dict] = []
        final_text: str = ""
        status_code = 200

        for iteration in range(self._PROJECT_CHAT_TOOL_MAX_ITERATIONS):
            status_code, msg = self._call_aoai_raw(
                chat_messages,
                tools=self._PROJECT_CHAT_TOOLS,
                max_tokens=1500,
                temperature=0.2,
            )
            if status_code != 200:
                final_text = msg if isinstance(msg, str) else str(msg)
                break
            if isinstance(msg, str):
                final_text = msg
                break

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                final_text = str(msg.get("content") or "").strip()
                break

            # Append the assistant's tool-call turn, then execute each tool.
            chat_messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
            })
            for call in tool_calls:
                tool_name = str(call.get("function", {}).get("name", ""))
                raw_args = str(call.get("function", {}).get("arguments", "{}"))
                try:
                    args = json.loads(raw_args) if raw_args else {}
                    if not isinstance(args, dict):
                        args = {}
                except Exception:
                    args = {}
                result = self._execute_project_chat_tool(project_root, slug, tool_name, args)
                tools_used.append({"name": tool_name, "args": args})
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": result,
                })
        else:
            # Loop exhausted without a terminal assistant message.
            final_text = (
                final_text
                or "⚠️ I used up my tool-call budget before I could finish. "
                "Try breaking the question into smaller pieces."
            )

        self._send_json(
            {
                "reply": final_text or "(no reply)",
                "slug": slug,
                "context_size": len(context_block),
                "tools_used": tools_used,
            },
            status_code,
        )

    # Shared Azure OpenAI caller used by BRD Copilot and Project Copilot.
    def _call_azure_openai(
        self,
        messages: list,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> tuple[int, str]:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
        auth = _aoai_auth_header()

        if not (endpoint and deployment and auth):
            return (
                200,
                "**Project Copilot is not configured on this portal.**\n\n"
                "Set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT` on the portal "
                "server. For auth, either set `AZURE_OPENAI_API_KEY`, or install "
                "`azure-identity` and sign in with `az login` so the portal can use "
                "your Entra ID identity.",
            )

        req_body: dict = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            req_body["response_format"] = response_format

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        req = Request(url, data=json.dumps(req_body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header(auth[0], auth[1])

        try:
            data = json.loads(_aoai_urlopen(req, timeout=60).decode("utf-8"))
            return 200, str(data["choices"][0]["message"]["content"]).strip()
        except URLError as e:
            logging.warning("Azure OpenAI call failed: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"
        except Exception as e:
            logging.warning("Azure OpenAI unexpected error: %s", e)
            return 502, f"Azure OpenAI call failed: {e}"

    def _safe_content_length(self) -> int | None:
        """Return validated content length or emit an error response."""
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "Invalid Content-Length"}, 400)
            return None

        if content_length <= 0:
            self._send_json({"error": "Missing request body"}, 400)
            return None

        if content_length > MAX_REQUEST_BYTES:
            self._send_json({"error": f"Payload too large (max {MAX_REQUEST_BYTES} bytes)"}, 413)
            return None

        return content_length

    def _client_ip(self) -> str:
        """Best-effort caller IP. Honors X-Forwarded-For if present (Easy Auth / ACA)."""
        fwd = self.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()
        try:
            return self.client_address[0]
        except Exception:
            return "unknown"

    def _rate_limit_key(self) -> str:
        """Prefer authenticated UPN; fall back to client IP."""
        upn = None
        try:
            upn = self._authorized_user()
        except Exception:
            upn = None
        return f"user:{upn}" if upn else f"ip:{self._client_ip()}"

    def _check_intake_rate_limit(self) -> bool:
        """Return True if the caller is allowed; otherwise emit 429 and return False."""
        allowed, retry_after = _INTAKE_LIMITER.check(self._rate_limit_key())
        if allowed:
            return True
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Retry-After", str(retry_after))
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Vary", "Origin")
        self.end_headers()
        body = json.dumps(
            {
                "error": "Rate limit exceeded",
                "limit": INTAKE_RATE_PER_MIN,
                "windowSeconds": INTAKE_RATE_WINDOW_SECONDS,
                "retryAfterSeconds": retry_after,
            }
        ).encode("utf-8")
        try:
            self.wfile.write(body)
        except Exception:
            pass
        return False

    def _handle_brd_intake(self):
        """Handle BRD intake submission (JSON body)"""
        if not self._check_intake_rate_limit():
            return
        content_type = self.headers.get("Content-Type", "")
        # Accept application/json with optional charset parameter. Reject
        # other content types outright so form posts can't bypass the JSON
        # schema check below.
        if not content_type.lower().split(";", 1)[0].strip() == "application/json":
            self._send_json({"error": "Expected Content-Type: application/json"}, 415)
            return
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self._send_json({"error": f"Invalid request: {e}"}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        raw_file_name = payload.get("fileName", "brd.md")
        if not isinstance(raw_file_name, str) or len(raw_file_name) > MAX_BRD_FILENAME_LEN:
            self._send_json(
                {"error": f"fileName must be a string of at most {MAX_BRD_FILENAME_LEN} characters"},
                400,
            )
            return

        try:
            file_name = _sanitize_brd_filename(raw_file_name)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        raw_content = payload.get("content", "")
        content, err = _validate_brd_content(raw_content)
        if err is not None:
            self._send_json({"error": err}, 400)
            return

        if not file_name or not content:
            self._send_json({"error": "Missing fileName or content"}, 400)
            return

        generation_options, options_error = _build_generation_options(
            payload,
            file_name=file_name,
            content=content,
        )
        if options_error is not None:
            self._send_json({"error": options_error}, 400)
            return

        return self._save_and_start_run(
            file_name, content, generation_options, owner=self._authorized_user()
        )

    def _save_and_start_run(self, file_name: str, content: str, generation_options: dict | None = None, owner: str | None = None):
        """Save intake document and launch pipeline worker thread."""
        brds_dir = FACTORY_REPO_ROOT / "docs" / "intake"
        brds_dir.mkdir(parents=True, exist_ok=True)
        brd_path = (brds_dir / file_name).resolve()

        if brds_dir.resolve() not in brd_path.parents:
            self._send_json({"error": "Resolved BRD path is outside intake directory"}, 400)
            return

        try:
            canonical_content = _build_generation_document(file_name, content, generation_options)
            brd_path.write_text(canonical_content, encoding="utf-8")
            logger.info(f"Saved BRD: {brd_path}")
        except Exception as e:
            self._send_json({"error": f"Failed to save BRD: {e}"}, 500)
            return

        # Create run entry
        run_id = str(uuid.uuid4())
        with RUNS_LOCK:
            RUNS[run_id] = {
                "id": run_id,
                "status": "queued",
                "createdAt": _utcnow_iso(),
                "brdFile": str(brd_path),
                "startedAt": None,
                "finishedAt": None,
                "returnCode": None,
                "stdout": None,
                "stderr": None,
                "command": None,
                "result": None,
                "generationOptions": generation_options or {},
                "owner": owner,
            }

        # Snapshot queued state and dispatch to bounded pipeline pool
        persist_runs()
        _PIPELINE_POOL.submit(
            self._run_pipeline,
            run_id,
            str(brd_path),
            generation_options or {},
            owner,
        )

        opts = generation_options or {}
        self._send_json(
            {
                "id": run_id,
                "status": "queued",
                "message": "Architecture source received and pipeline started.",
                "brdFile": f"docs/intake/{file_name}",
                "sourceType": opts.get("sourceType", "brd-markdown"),
                "sourceTypeRequested": opts.get("sourceTypeRequested"),
                "sourceTypeDetected": opts.get("sourceTypeDetected"),
                "targetProjectSlug": opts.get("targetProjectSlug"),
            },
            202,
        )

    def _handle_agent_foundry_run_create(self):
        """Create a bounded Agent Foundry planning run for portal approval."""
        if not self._check_intake_rate_limit():
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().split(";", 1)[0].strip() == "application/json":
            self._send_json({"error": "Expected Content-Type: application/json"}, 415)
            return

        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as exc:
            self._send_json({"error": f"Invalid request: {exc}"}, 400)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        source_type = str(payload.get("sourceType") or "brd-prd").strip().lower()
        allowed_source_types = {
            "brd-prd",
            "architecture-markdown",
            "architecture-mermaid",
            "architecture-drawio",
            "architecture-visio",
            "learning-plan",
        }
        if source_type not in allowed_source_types:
            self._send_json(
                {
                    "error": "sourceType must be brd-prd, architecture-markdown, architecture-mermaid, architecture-drawio, architecture-visio, or learning-plan"
                },
                400,
            )
            return

        title = str(payload.get("title") or "Agent Foundry portal run").strip()[:120]
        content = str(payload.get("content") or "").strip()
        if len(content) < MIN_BRD_CONTENT_CHARS:
            self._send_json({"error": f"content must be at least {MIN_BRD_CONTENT_CHARS} characters"}, 400)
            return
        if len(content) > MAX_BRD_CONTENT_CHARS:
            self._send_json({"error": f"content must be at most {MAX_BRD_CONTENT_CHARS} characters"}, 413)
            return

        diagram_file_name = str(payload.get("diagramFileName") or "").strip()[:180]
        run_id = str(uuid.uuid4())
        plan = _build_agent_foundry_plan(source_type, title, content)
        if diagram_file_name:
            plan["diagramFileName"] = pathlib.Path(diagram_file_name).name
        now = _utcnow_iso()
        with RUNS_LOCK:
            RUNS[run_id] = {
                "id": run_id,
                "kind": "agent-foundry",
                "status": "planning_ready",
                "createdAt": now,
                "startedAt": now,
                "finishedAt": None,
                "returnCode": None,
                "stderr": None,
                "owner": self._authorized_user(),
                "agentFoundry": {
                    "title": title,
                    "sourceType": source_type,
                    "diagramFileName": pathlib.Path(diagram_file_name).name if diagram_file_name else None,
                    "contentPreview": content[:1200],
                    "approvedAt": None,
                    "approvedBy": None,
                    "plan": plan,
                    "evidence": [],
                },
                "result": {
                    "status": "planning_ready",
                    "message": "Agent Foundry plan is ready for human approval.",
                    "plan": plan,
                },
            }
            _persist_runs_unlocked()
            safe_run = _safe_agent_foundry_run(RUNS[run_id])

        self._send_json(safe_run, 201)

    def _handle_agent_foundry_run_status(self, run_id: str):
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run or run.get("kind") != "agent-foundry":
            self._send_json({"error": "Agent Foundry run not found"}, 404)
            return

        self._send_json(_safe_agent_foundry_run(run), 200)

    def _handle_agent_foundry_runs_list(self):
        with RUNS_LOCK:
            runs = [run for run in RUNS.values() if run.get("kind") == "agent-foundry"]

        safe_runs = [
            _safe_agent_foundry_run(run, include_plan=False)
            for run in sorted(runs, key=lambda item: item.get("createdAt") or "", reverse=True)
        ]
        self._send_json({"runs": safe_runs}, 200)

    def _handle_agent_foundry_run_approve(self, run_id: str):
        with RUNS_LOCK:
            run = RUNS.get(run_id)
            if not run or run.get("kind") != "agent-foundry":
                self._send_json({"error": "Agent Foundry run not found"}, 404)
                return
            if run.get("status") not in {"planning_ready", "approved", "completed"}:
                self._send_json({"error": f"Run cannot be approved from status {run.get('status')}"}, 409)
                return

            agent_payload = run.setdefault("agentFoundry", {})
            plan = agent_payload.get("plan") or {}
            evidence = _build_agent_foundry_evidence(plan)
            now = _utcnow_iso()
            run["status"] = "completed"
            run["finishedAt"] = now
            run["returnCode"] = 0
            agent_payload["approvedAt"] = now
            agent_payload["approvedBy"] = self._authorized_user()
            agent_payload["evidence"] = evidence
            run["result"] = {
                "status": "completed",
                "message": "Approved Agent Foundry execution package is ready. Run the handoff prompts in VS Code or connect a hosted runner before enabling command execution.",
                "plan": plan,
                "evidence": evidence,
            }
            _persist_runs_unlocked()
            safe_run = _safe_agent_foundry_run(run)

        self._send_json(safe_run, 200)

    def _run_pipeline(self, run_id, brd_path, generation_options=None, owner: str | None = None):
        """Execute the pipeline in background with resilience (retry + circuit breaker)"""
        tracer = get_tracer("aaf-portal.pipeline")
        with tracer.start_as_current_span("brd.pipeline") as span:
            span.set_attribute("aaf.run_id", run_id)
            span.set_attribute("aaf.brd_path", str(brd_path))
            if owner:
                span.set_attribute("aaf.owner", owner)

            with RUNS_LOCK:
                RUNS[run_id]["status"] = "running"
                RUNS[run_id]["startedAt"] = _utcnow_iso()
                _persist_runs_unlocked()

            try:
                # Execute BRD processing with automatic retry + circuit breaker
                output = _BRD_EXECUTOR.execute(
                    process_brd_document,
                    FACTORY_REPO_ROOT,
                    pathlib.Path(brd_path),
                    run_id,
                    generation_options or {},
                )

                # Enforce BRD readiness gate when runtime:auto is explicitly requested.
                gate_violation = _runtime_auto_gate_violation(generation_options, output)
                if gate_violation:
                    raise RuntimeError(gate_violation)

                # Stamp the submitter as owner of the generated project so per-user
                # filtering (Entra auth mode) gives them access. Best-effort only.
                if owner and isinstance(output, dict):
                    slug = output.get("slug") or output.get("projectSlug")
                    if slug:
                        try:
                            data = _load_owners()
                            projects = data.setdefault("projects", {})
                            existing = projects.get(slug) or []
                            if isinstance(existing, str):
                                existing = [existing]
                            lowered = {e.strip().lower() for e in existing if isinstance(e, str)}
                            if owner.strip().lower() not in lowered:
                                existing.append(owner)
                                projects[slug] = existing
                                _save_owners(data)
                                logger.info("Recorded owner %s for project %s", owner, slug)
                        except Exception as exc:  # noqa: BLE001 - best-effort
                            logger.warning("Failed to persist owner for %s: %s", slug, exc)

                # Persist the new project artifacts + updated feed + owners to
                # blob storage so they survive container restarts. No-op when
                # FACTORY_PORTAL_BLOB_ACCOUNT is unset (local dev).
                if blob_sync.BLOB_ENABLED and isinstance(output, dict):
                    slug = output.get("slug") or output.get("projectSlug")
                    try:
                        if slug:
                            project_dir = FACTORY_REPO_ROOT / "projects" / slug
                            blob_sync.upload_project(project_dir, slug)
                        blob_sync.upload_feed(
                            FACTORY_REPO_ROOT / "factory-projects.generated.json"
                        )
                        if OWNERS_FILE.is_file():
                            blob_sync.upload_owners(OWNERS_FILE)
                    except Exception as exc:  # noqa: BLE001 - best-effort
                        logger.warning("Blob upload after run %s failed: %s", run_id, exc)

                with RUNS_LOCK:
                    RUNS[run_id].update(
                        {
                            "status": "completed",
                            "finishedAt": _utcnow_iso(),
                            "returnCode": 0,
                            "stdout": None,
                            "stderr": None,
                            "command": "azure_native_factory_runner",
                            "result": output,
                        }
                    )
                    _persist_runs_unlocked()

                span.set_attribute("aaf.status", "completed")
                logger.info(f"Pipeline completed for run {run_id}: returnCode=0")
            except Exception as e:
                logger.exception(f"Pipeline error for run {run_id}: {e}")
                span.set_attribute("aaf.status", "failed")
                span.record_exception(e)
                with RUNS_LOCK:
                    RUNS[run_id].update(
                        {
                            "status": "failed",
                            "finishedAt": _utcnow_iso(),
                            "returnCode": -1,
                            "stderr": str(e),
                            "result": {"status": "failed", "message": str(e)},
                        }
                    )
                    _persist_runs_unlocked()

    # ── Repo Intake ─────────────────────────────────────────────────────────

    def _handle_repo_intake(self):
        """Handle a repository analysis or enhancement intake request.

        Expected JSON body::

            {
                "inputSource":    "remote" | "local",                 // optional, default: remote
                "repoUrl":        "https://github.com/owner/repo",
                "localRepoPath":  "C:/src/my-repo",                    // required when inputSource=local
                "token":          "<PAT>",
                "workflowMode":   "analysis-only" | "implement-pr",   // optional, default: analysis-only
                "automationGoal": "Add a notification workflow",       // optional
                "branchSuffix":   "analysis-2026-04-24"                // optional
            }

        **analysis-only** (default): Clones the repo, creates an ``AAF-<branchSuffix>``
        branch, analyses the repository content (README, architecture files, tech stack,
        code inventory), writes ``AAF-analysis-report.md``, commits, and pushes.

        **implement-pr**: All of the above, then runs the dedicated ``repo-change-agent``
        inside the cloned repo, commits all resulting changes, pushes the branch, and
        opens a pull request on GitHub or Azure DevOps.

        All git work is done in a background thread; returns ``202 Accepted``
        immediately with a run ID that can be polled via ``GET /api/runs/<id>``.
        """
        if not self._check_intake_rate_limit():
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().split(";", 1)[0].strip() == "application/json":
            self._send_json({"error": "Expected Content-Type: application/json"}, 415)
            return
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as exc:
            self._send_json({"error": f"Invalid request: {exc}"}, 400)
            return
        if not isinstance(payload, dict):
            self._send_json({"error": "Request body must be a JSON object"}, 400)
            return

        input_source = str(payload.get("inputSource") or "remote").strip().lower()
        if input_source not in {"remote", "local"}:
            self._send_json({"error": "inputSource must be 'remote' or 'local'"}, 400)
            return

        local_repo_path: pathlib.Path | None = None
        repo_url = ""

        if input_source == "local":
            if not ALLOW_LOCAL_REPO_INTAKE:
                self._send_json(
                    {"error": "Local repository intake is disabled on this deployment"},
                    403,
                )
                return
            local_repo_path, local_err = _validate_local_repo_path(payload.get("localRepoPath", ""))
            if local_err:
                self._send_json({"error": local_err}, 400)
                return
            repo_url = f"local://{local_repo_path.name}"
        else:
            # Validate repoUrl
            repo_url, url_err = _validate_repo_url(payload.get("repoUrl", ""))
            if url_err:
                self._send_json({"error": url_err}, 400)
                return

        workflow_mode, mode_err = _sanitize_repo_workflow_mode(payload.get("workflowMode"))
        if mode_err:
            self._send_json({"error": mode_err}, 400)
            return

        pat = ""
        if input_source == "remote":
            # Validate PAT (non-empty string, max 500 chars)
            raw_token = payload.get("token", "")
            if not isinstance(raw_token, str) or not raw_token.strip():
                self._send_json({"error": "token (PAT) is required for remote repositories"}, 400)
                return
            pat = raw_token.strip()
            if len(pat) > 500:
                self._send_json({"error": "token must be at most 500 characters"}, 400)
                return

        automation_goal, goal_err = _sanitize_repo_automation_goal(payload.get("automationGoal"))
        if goal_err:
            self._send_json({"error": goal_err}, 400)
            return

        # Validate / default branchSuffix
        raw_suffix = payload.get("branchSuffix", "").strip()
        if not raw_suffix:
            # Default: date-based suffix
            raw_suffix = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        branch_suffix, suffix_err = _sanitize_branch_suffix(raw_suffix)
        if suffix_err:
            self._send_json({"error": suffix_err}, 400)
            return
        branch_name = f"AAF-{branch_suffix}"

        run_id = str(uuid.uuid4())
        owner = self._authorized_user()
        with RUNS_LOCK:
            RUNS[run_id] = {
                "id": run_id,
                "status": "queued",
                "createdAt": _utcnow_iso(),
                "brdFile": None,
                "startedAt": None,
                "finishedAt": None,
                "returnCode": None,
                "stdout": None,
                "stderr": None,
                "command": "repo-analysis",
                "result": None,
                "generationOptions": {
                    "sourceType": "repo-analysis-local" if input_source == "local" else "repo-analysis",
                    "inputSource": input_source,
                    "repoUrl": repo_url,    # credential-free URL safe to store
                    "localRepoName": local_repo_path.name if local_repo_path else "",
                    "branchName": branch_name,
                    "workflowMode": workflow_mode,
                    "automationGoal": automation_goal,
                },
                "owner": owner,
            }
        persist_runs()

        _PIPELINE_POOL.submit(
            self._run_repo_analysis,
            run_id,
            repo_url,
            pat,          # PAT is passed only to the worker; never stored in RUNS
            branch_name,
            workflow_mode,
            automation_goal,
            owner,
            local_repo_path=local_repo_path,
            input_source=input_source,
        )

        self._send_json(
            {
                "id": run_id,
                "status": "queued",
                "message": "Repository intake accepted. Analysis running in background.",
                "repoUrl": repo_url,
                "inputSource": input_source,
                "branchName": branch_name,
                "workflowMode": workflow_mode,
            },
            202,
        )

    def _run_repo_analysis(
        self,
        run_id: str,
        repo_url: str,
        pat: str,
        branch_name: str,
        workflow_mode: str = "analysis-only",
        automation_goal: str = "",
        requested_by: str = "",
        local_repo_path: pathlib.Path | None = None,
        input_source: str = "remote",
    ) -> None:
        """Background worker: clone → branch → analyse → optional implement → push → PR."""
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "running"
            RUNS[run_id]["startedAt"] = _utcnow_iso()
            _persist_runs_unlocked()
        _set_run_progress(run_id, stage="queued", message="Preparing repository workflow")

        tmp_dir: str | None = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix="aaf-repo-")
            clone_url = ""
            if local_repo_path:
                clone_url = str(local_repo_path)

                _set_run_progress(run_id, stage="clone", message="Cloning local repository")
                ok, err = _clone_local_repo(clone_url, tmp_dir)
                if not ok:
                    raise RuntimeError(err)

                _set_run_progress(run_id, stage="default-branch", message="Detecting repository default branch")
                default_branch, default_branch_err = _detect_default_branch(tmp_dir)
                if default_branch_err:
                    logger.warning("Local repo intake default branch detection warning for %s: %s", local_repo_path, default_branch_err)

                _set_run_progress(run_id, stage="branch", message=f"Creating working branch {branch_name} in the local repository")
                ok, err = _create_aaf_branch(tmp_dir, branch_name, clone_url)
                if not ok:
                    raise RuntimeError(err)
            else:
                clone_url = _make_authed_clone_url(repo_url, pat)

                # 1. Clone
                _set_run_progress(run_id, stage="clone", message="Cloning target repository")
                ok, err = _clone_repo(clone_url, tmp_dir)
                if not ok:
                    raise RuntimeError(err)

                _set_run_progress(run_id, stage="default-branch", message="Detecting repository default branch")
                default_branch, default_branch_err = _detect_default_branch(tmp_dir)
                if default_branch_err:
                    logger.warning("Repo intake default branch detection warning for %s: %s", repo_url, default_branch_err)

                # 2. Create AAF branch
                _set_run_progress(run_id, stage="branch", message=f"Creating working branch {branch_name}")
                ok, err = _create_aaf_branch(tmp_dir, branch_name, clone_url)
                if not ok:
                    raise RuntimeError(err)

            # 3. Analyse repo content
            _set_run_progress(run_id, stage="analysis", message="Analyzing repository contents and architecture signals")
            analysis = _walk_repo_for_analysis(tmp_dir)

            # 4. Build report
            _set_run_progress(run_id, stage="report", message="Writing repository analysis report")
            report = _build_repo_analysis_report(repo_url, branch_name, analysis)

            report_path = pathlib.Path(tmp_dir) / _AAF_ANALYSIS_REPORT_FILE
            report_path.write_text(report, encoding="utf-8")

            pr_url = ""
            summary_url = ""
            report_url = ""
            if not local_repo_path:
                report_url = _build_remote_file_url(repo_url, branch_name, _AAF_ANALYSIS_REPORT_FILE) or ""
            copilot_run_id = ""
            project_slug = ""
            project_title = ""
            project_persist_error = ""

            if workflow_mode == "implement-pr":
                if copilot_runner is None:
                    raise RuntimeError("Copilot CLI runner is not available on this build")
                prompt = _build_repo_change_prompt(
                    repo_url,
                    branch_name,
                    analysis,
                    automation_goal=automation_goal,
                )
                metadata = copilot_runner.start_run(
                    pathlib.Path(tmp_dir),
                    prompt,
                    requested_by=requested_by,
                    agent=_AAF_REPO_CHANGE_AGENT,
                )
                copilot_run_id = str(metadata.get("runId") or "")
                _set_run_progress(run_id, stage="repo-change-agent", message="Repo change agent is reviewing and modifying the repository")
                run, wait_err = _wait_for_repo_copilot_run(
                    pathlib.Path(tmp_dir),
                    copilot_run_id,
                    run_id,
                )
                if wait_err:
                    raise RuntimeError(wait_err)
                if (run or {}).get("status") != "succeeded":
                    log_tail = copilot_runner.read_log_tail(pathlib.Path(tmp_dir), copilot_run_id) or ""
                    raise RuntimeError(
                        "Copilot repo workflow did not finish successfully: "
                        f"{(run or {}).get('status', 'unknown')}\n{log_tail[-1200:]}"
                    )
                _remove_repo_copilot_artifacts(pathlib.Path(tmp_dir), copilot_run_id)
                _ensure_change_summary(tmp_dir, automation_goal, copilot_run_id)
                _set_run_progress(
                    run_id,
                    stage="commit",
                    message="Committing repository changes to the working branch",
                )
                ok, err = _commit_and_push_all_changes(
                    tmp_dir,
                    branch_name,
                    clone_url,
                    "feat: add AAF architecture-aligned repository enhancements",
                )
                if not ok:
                    raise RuntimeError(err)
                if local_repo_path:
                    _set_run_progress(
                        run_id,
                        stage="report-ready",
                        message="Repository changes committed to the local working branch",
                    )
                else:
                    summary_url = _build_remote_file_url(repo_url, branch_name, _AAF_CHANGE_SUMMARY_FILE) or ""
                    pr_title = _build_repo_pr_title(repo_url, automation_goal)
                    pr_body = _build_repo_pr_body(branch_name, default_branch, automation_goal)
                    _set_run_progress(run_id, stage="pr", message="Creating pull request")
                    pr_url, pr_err = _create_pull_request(
                        repo_url,
                        pat,
                        branch_name,
                        default_branch,
                        pr_title,
                        pr_body,
                    )
                    if pr_err:
                        raise RuntimeError(f"Branch was pushed but PR creation failed: {pr_err}")
            else:
                if local_repo_path:
                    _set_run_progress(run_id, stage="push-report", message="Committing analysis report to the local working branch")
                    ok, err = _commit_and_push_report(tmp_dir, report, branch_name, clone_url)
                    if not ok:
                        raise RuntimeError(err)
                    _set_run_progress(
                        run_id,
                        stage="report-ready",
                        message="Analysis report committed to the local working branch",
                    )
                else:
                    # 5. Commit and push report
                    _set_run_progress(run_id, stage="push-report", message="Pushing AAF analysis report to the working branch")
                    ok, err = _commit_and_push_report(tmp_dir, report, branch_name, clone_url)
                    if not ok:
                        raise RuntimeError(err)

            _set_run_progress(
                run_id,
                stage="project-sync",
                message="Persisting imported repository snapshot for portal project tools",
            )
            slug, title, persist_err = _persist_repo_intake_project(
                pathlib.Path(tmp_dir),
                repo_url=repo_url,
                branch_name=branch_name,
                workflow_mode=workflow_mode,
                automation_goal=automation_goal,
                run_id=run_id,
                requested_by=requested_by,
                analysis=analysis,
            )
            if persist_err:
                logger.warning("Repo-intake project persistence failed for run %s: %s", run_id, persist_err)
                project_persist_error = persist_err
            else:
                project_slug = slug or ""
                project_title = title or ""
                # Project snapshot was moved to projects/<slug>; skip temp cleanup.
                tmp_dir = None

            with RUNS_LOCK:
                RUNS[run_id].update({
                    "status": "completed",
                    "finishedAt": _utcnow_iso(),
                    "returnCode": 0,
                    "result": {
                        "status": "completed",
                        "repoUrl": repo_url,
                        "inputSource": input_source,
                        "branchName": branch_name,
                        "branchTarget": "local" if local_repo_path else "remote",
                        "branchCommitted": True,
                        "branchCommitMode": "all-changes" if workflow_mode == "implement-pr" else "analysis-report-only",
                        "workflowMode": workflow_mode,
                        "baseBranch": default_branch,
                        "reportFile": _AAF_ANALYSIS_REPORT_FILE,
                        "reportUrl": report_url,
                        "summaryFile": _AAF_CHANGE_SUMMARY_FILE if workflow_mode == "implement-pr" else "",
                        "summaryUrl": summary_url,
                        "prUrl": pr_url,
                        "copilotRunId": copilot_run_id,
                        "projectSlug": project_slug,
                        "projectTitle": project_title,
                        "projectPersistError": project_persist_error,
                        "techStack": analysis.get("tech_stack", []),
                        "archFilesFound": len(analysis.get("arch_files", [])),
                        "fileCountsByLanguage": analysis.get("file_counts", {}),
                    },
                })
                _persist_runs_unlocked()
            _set_run_progress(run_id, stage="completed", message="Repository workflow completed successfully")
            logger.info("Repo analysis completed for run %s branch %s", run_id, branch_name)

        except Exception as exc:
            logger.exception("Repo analysis failed for run %s: %s", run_id, exc)
            with RUNS_LOCK:
                RUNS[run_id].update({
                    "status": "failed",
                    "finishedAt": _utcnow_iso(),
                    "returnCode": -1,
                    "stderr": str(exc),
                    "result": {"status": "failed", "message": str(exc)},
                })
                _persist_runs_unlocked()
        finally:
            # Always clean up the temp clone directory
            if tmp_dir and pathlib.Path(tmp_dir).exists():
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

    def _handle_brd_upload(self):
        """Handle multipart/form-data BRD file upload."""
        if not self._check_intake_rate_limit():
            return
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json({"error": "Expected multipart/form-data"}, 415)
            return

        content_length = self._safe_content_length()
        if content_length is None:
            return
        raw_body = self.rfile.read(content_length)

        try:
            fields = _parse_multipart_form(content_type, raw_body)
        except Exception as exc:
            self._send_json({"error": f"Failed to parse multipart body: {exc}"}, 400)
            return

        project_name_field = (fields.get("project_name") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        enable_observability_field = (fields.get("enable_observability") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        generate_infra_field = (fields.get("generate_infra") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        run_security_audit_field = (fields.get("run_security_audit") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        network_tier_field = (fields.get("network_tier") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        implementation_language_field = _sanitize_implementation_language(
            (fields.get("implementation_language") or {}).get("data", b"").decode("utf-8", errors="replace")
        )
        iac_tool_field = (fields.get("iac_tool") or {}).get("data", b"").decode("utf-8", errors="replace").strip().lower()
        source_type_field = (fields.get("source_type") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        target_project_slug_field = (fields.get("target_project_slug") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        deployment_mode_field = (fields.get("deployment_mode") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        aca_express_region_field = (fields.get("aca_express_region") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        aca_express_image_field = (fields.get("aca_express_image") or {}).get("data", b"").decode("utf-8", errors="replace").strip()
        inline_content_field = (fields.get("content") or {}).get("data", b"").decode("utf-8", errors="replace")
        brd_field = fields.get("brd_file")

        if not brd_field:
            self._send_json({"error": "Missing brd_file field"}, 400)
            return

        uploaded_filename = brd_field.get("filename") or "brd.md"
        try:
            if project_name_field:
                file_name = _sanitize_brd_filename(project_name_field)
            else:
                file_name = _sanitize_brd_filename(uploaded_filename)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        generation_options, options_error = _build_generation_options(
            {
                "enableObservability": enable_observability_field,
                "generateInfra": generate_infra_field,
                "runSecurityAudit": run_security_audit_field,
                "networkTier": network_tier_field,
                "implementationLanguage": implementation_language_field,
                "iacTool": iac_tool_field,
                "sourceType": source_type_field,
                "targetProjectSlug": target_project_slug_field,
                "deploymentMode": deployment_mode_field,
                "acaExpressRegion": aca_express_region_field,
                "acaExpressImage": aca_express_image_field,
            },
            file_name=file_name,
            content=inline_content_field,
            uploaded_file_name=uploaded_filename,
            raw_bytes=raw_uploaded_bytes,
        )
        if options_error is not None:
            self._send_json({"error": options_error}, 400)
            return

        source_type = _sanitize_source_type(generation_options.get("sourceType"))
        raw_uploaded_bytes = brd_field.get("data") or b""
        uploaded_text = None
        if source_type in _TEXTUAL_SOURCE_TYPES:
            try:
                uploaded_text = raw_uploaded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                uploaded_text = None

        source_text_candidate = uploaded_text if uploaded_text and uploaded_text.strip() else inline_content_field
        content, err = _validate_brd_content(source_text_candidate)
        if err is not None:
            if source_type in _REFERENCE_ONLY_SOURCE_TYPES:
                self._send_json(
                    {"error": "Provide a written architecture summary when uploading Visio or Lucidchart artifacts."},
                    400,
                )
                return
            if source_type in _TEXTUAL_SOURCE_TYPES and uploaded_text is None:
                self._send_json({"error": "Uploaded file must be UTF-8 text for the selected source type"}, 400)
                return
            self._send_json({"error": err}, 400)
            return

        if implementation_language_field:
            generation_options["implementationLanguage"] = implementation_language_field
        if iac_tool_field:
            generation_options["iacTool"] = iac_tool_field
        if source_type != "brd-markdown":
            generation_options["sourceFileName"] = uploaded_filename
            generation_options["sourceAttachment"] = _save_source_attachment(
                FACTORY_REPO_ROOT / "docs" / "intake",
                file_name,
                source_type,
                uploaded_filename,
                raw_uploaded_bytes,
            )

        return self._save_and_start_run(
            file_name, content, generation_options, owner=self._authorized_user()
        )

    def _handle_run_status(self, run_id):
        """Handle run status query"""
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run:
            self._send_json({"error": "Run not found"}, 404)
            return

        # Return a sanitized status payload to avoid leaking command output and local paths.
        safe_run = {
            "id": run.get("id"),
            "status": run.get("status"),
            "createdAt": run.get("createdAt"),
            "startedAt": run.get("startedAt"),
            "finishedAt": run.get("finishedAt"),
            "returnCode": run.get("returnCode"),
            "stderr": run.get("stderr"),
            "generationOptions": run.get("generationOptions") or {},
            "progress": run.get("progress") or {},
            "result": run.get("result"),
        }
        self._send_json(safe_run, 200)

    def _handle_run_log(self, run_id):
        """Return the retained plain-text log tail for a tracked run."""
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run:
            self._send_json({"error": "Run not found"}, 404)
            return

        log_text = str(
            run.get("logTail")
            or run.get("progress", {}).get("logPreview")
            or run.get("stderr")
            or ""
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        body = log_text.encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_runs_list(self):
        """Handle list of all tracked runs."""
        with RUNS_LOCK:
            runs = list(RUNS.values())

        safe_runs = []
        for run in sorted(runs, key=lambda item: item.get("createdAt") or "", reverse=True):
            safe_runs.append(
                {
                    "id": run.get("id"),
                    "brdFile": pathlib.Path(run.get("brdFile") or "").name,
                    "status": run.get("status"),
                    "createdAt": run.get("createdAt"),
                    "startedAt": run.get("startedAt"),
                    "finishedAt": run.get("finishedAt"),
                    "returnCode": run.get("returnCode"),
                }
            )

        self._send_json({"runs": safe_runs}, 200)

    def _handle_run_project(self, run_id):
        """Return the generated project payload for a specific run."""
        with RUNS_LOCK:
            run = RUNS.get(run_id)

        if not run:
            self._send_json({"error": "Run not found"}, 404)
            return

        safe_run = {
            "id": run.get("id"),
            "status": run.get("status"),
            "createdAt": run.get("createdAt"),
            "startedAt": run.get("startedAt"),
            "finishedAt": run.get("finishedAt"),
            "returnCode": run.get("returnCode"),
            "result": run.get("result"),
        }

        result = run.get("result") or {}
        response = {
            "run": safe_run,
            "project": result.get("project"),
            "analysis": result.get("analysis"),
        }

        if run.get("status") in {"queued", "running"}:
            self._send_json(response, 202)
            return

        if not result:
            response["warning"] = "Run completed without a project payload"

        self._send_json(response, 200)

    def _serve_json_feed(self):
        """Serve the generated project feed.

        Merges two sources so the feed is always live:
        1. factory-projects.generated.json — baked-in snapshot or persisted feed
        2. Live scan of the projects/ directory — picks up any project whose
           project-manifest.json exists but isn't yet recorded in the JSON file.

        This means newly generated projects appear immediately without requiring
        a container rebuild or volume mount on remote deployments.
        """
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"

        # Load the persisted feed (may be the baked-in image snapshot or empty).
        baked_projects: list[dict] = []
        generated_at: str | None = None
        if feed_path.exists() and feed_path.is_file():
            try:
                persisted = json.loads(feed_path.read_text(encoding="utf-8"))
                baked_projects = persisted.get("projects") or []
                generated_at = persisted.get("generatedAt")
            except json.JSONDecodeError as exc:
                logger.warning("Failed to read project feed: %s", exc)

        # Build a slug→record index from the baked feed.
        index: dict[str, dict] = {p["slug"]: p for p in baked_projects if p.get("slug")}

        # Live scan: visit every subdirectory of projects/ that has a manifest.
        projects_dir = FACTORY_REPO_ROOT / "projects"
        if projects_dir.is_dir():
            for manifest_path in sorted(projects_dir.glob("*/project-manifest.json")):
                slug = manifest_path.parent.name
                if slug in index:
                    continue  # already present from persisted feed
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                # Reconstruct a minimal project record from the manifest.
                index[slug] = {
                    "slug": slug,
                    "title": manifest.get("title", slug),
                    "status": manifest.get("status", "Ready"),
                    "generatedFrom": manifest.get("source_brd", ""),
                    "generatedAt": manifest.get("created_at", ""),
                    "options": manifest.get("generation_options", {}),
                    "links": manifest.get("links", {}) if isinstance(manifest.get("links"), dict) else {},
                    "suggestedRuntime": manifest.get("suggested_runtime"),
                    "brdReadiness": manifest.get("brd_readiness"),
                    "orchestratorAutoFlow": manifest.get("orchestrator_auto_flow"),
                    "implementationLanguage": manifest.get("implementation_language"),
                    "iacTool": manifest.get("iac_tool"),
                }

        # Sort newest-first by generatedAt.
        merged = sorted(
            index.values(),
            key=lambda p: p.get("generatedAt") or "",
            reverse=True,
        )

        # Drop ghost entries: persisted feed sometimes lists slugs whose
        # projects/<slug>/ directory was deleted or never synced. If the UI
        # links users to those slugs, every subsequent API call (chat, files,
        # analysis) 404s. Filter them out here so the feed only ever advertises
        # projects we can actually serve.
        # EXCEPTION: if projects/ is empty or missing entirely, assume this is
        # a snapshot deployment (baked-in feed) and skip filtering.
        if projects_dir.is_dir() and any(projects_dir.iterdir()):
            merged = [p for p in merged if (projects_dir / (p.get("slug") or "")).is_dir()]

        # Apply per-deployment visibility allowlist (hides hidden projects on
        # the hosted/external portal). No-op when unset.
        if VISIBLE_SLUGS is not None:
            merged = [p for p in merged if _is_slug_visible(p.get("slug", ""))]

        # Apply per-user ownership filtering when Entra auth is active.
        if AUTH_MODE == "entra":
            user = self._authorized_user()
            merged = [p for p in merged if _user_can_see_project(p.get("slug", ""), user)]
            # Annotate each record with the current user's role for UI hints.
            for p in merged:
                p["_yours"] = bool(user) and user.strip().lower() in _project_owners(p.get("slug", ""))

        payload = {
            "generatedAt": generated_at,
            "projects": merged,
        }
        return self._send_json(payload, 200)

    def _serve_factory_template_file(self, request_path: str):
        """Serve files from factory-templates/ directory.
        
        Request path like /factory-templates/application-zone/GPS_ONBOARDING_FOR_NEW_APPS.md
        maps to factory-templates/application-zone/GPS_ONBOARDING_FOR_NEW_APPS.md
        
        Markdown files are automatically rendered as HTML with client-side markdown renderer.
        """
        # Extract relative path after /factory-templates/
        rel_path = request_path[len("/factory-templates/"):]
        
        # Validate path (no directory traversal)
        if ".." in rel_path or rel_path.startswith("/"):
            self.send_error(400, "Invalid path")
            return
        
        file_path = (FACTORY_REPO_ROOT / "factory-templates" / rel_path).resolve()
        templates_root = (FACTORY_REPO_ROOT / "factory-templates").resolve()
        
        # Ensure the resolved path is within factory-templates/
        if templates_root not in file_path.parents and file_path.parent != templates_root:
            self.send_error(403, "Forbidden")
            return
        
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not Found")
            return
        
        try:
            content = file_path.read_bytes()
            
            # For markdown files, wrap in HTML with client-side renderer
            if file_path.suffix == ".md":
                markdown_text = content.decode('utf-8')
                # Escape HTML special characters in markdown
                markdown_escaped = html.escape(markdown_text)
                
                html_wrapper = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(file_path.stem)}</title>
    <script src="https://cdn.jsdelivr.net/npm/markdown-it@14/dist/markdown-it.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 40px 20px; background: white; min-height: 100vh; }}
        h1, h2, h3, h4, h5, h6 {{ margin-top: 24px; margin-bottom: 16px; font-weight: 600; line-height: 1.25; }}
        h1 {{ font-size: 2em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; }}
        h3 {{ font-size: 1.25em; }}
        p {{ margin-bottom: 16px; }}
        ul, ol {{ margin-left: 2em; margin-bottom: 16px; }}
        li {{ margin-bottom: 8px; }}
        code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 3px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 0.9em; }}
        pre {{ background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; margin-bottom: 16px; }}
        pre code {{ background: none; padding: 0; }}
        blockquote {{ border-left: 4px solid #ddd; padding-left: 16px; margin: 16px 0; color: #666; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #f6f8fa; font-weight: 600; }}
        a {{ color: #0366d6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .back-link {{ margin-bottom: 20px; }}
        .back-link a {{ font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="back-link">
            <a href="javascript:history.back()">← Back</a>
        </div>
        <div id="content"></div>
    </div>
    <script>
        const md = new markdownit({{
            html: false,
            linkify: true,
            typographer: true
        }});
        const markdown = `{markdown_escaped}`;
        const html = md.render(markdown);
        document.getElementById('content').innerHTML = html;
    </script>
</body>
</html>"""
                content = html_wrapper.encode('utf-8')
                content_type = "text/html; charset=utf-8"
            elif file_path.suffix == ".json":
                content_type = "application/json"
            elif file_path.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            else:
                content_type = "text/plain; charset=utf-8"
            
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", len(content))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(content)
        except (OSError, IOError) as e:
            logger.error("Error serving factory template file %s: %s", file_path, e)
            self.send_error(500, "Internal Server Error")

    def _resolve_project_root(self, slug: str) -> pathlib.Path | None:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", slug or ""):
            return None
        if not _user_can_see_project(slug, self._authorized_user()):
            return None
        project_root = (FACTORY_REPO_ROOT / "projects" / slug).resolve()
        projects_root = (FACTORY_REPO_ROOT / "projects").resolve()
        if projects_root not in project_root.parents:
            return None
        if not project_root.exists() or not project_root.is_dir():
            return None
        return project_root

    def _handle_guide_refresh(self):
        """Regenerate docs/guide-report.md for a project and patch the feed."""
        content_length = self._safe_content_length()
        if content_length is None:
            return
        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception as exc:
            return self._send_json({"error": f"Invalid request: {exc}"}, 400)

        slug = str(payload.get("slug", "")).strip()
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        try:
            from generate_guide_report import generate_guide_report  # type: ignore
        except ModuleNotFoundError:
            from scripts.generate_guide_report import generate_guide_report  # type: ignore

        try:
            info = generate_guide_report(project_root)
        except Exception as exc:  # pragma: no cover - defensive
            return self._send_json({"error": f"Guide generation failed: {exc}"}, 500)

        # Convert report path to a repo-relative forward-slash URL for the portal.
        try:
            rel_path = str(
                pathlib.Path(info["report_path"]).resolve().relative_to(FACTORY_REPO_ROOT)
            ).replace("\\", "/")
        except ValueError:
            rel_path = info["report_path"]

        guide_block = {
            "path": rel_path,
            "generated_at": info.get("generated_at"),
            "severity_counts": info.get("severity_counts", {}),
        }

        # Patch project-manifest.json.
        manifest_path = project_root / "project-manifest.json"
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = {}
            manifest["guide_report"] = guide_block
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

        # Patch factory-projects.generated.json if the project has a feed entry.
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"
        if feed_path.is_file():
            try:
                feed = json.loads(feed_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                feed = {}
            changed = False
            for record in feed.get("projects") or []:
                if isinstance(record, dict) and record.get("slug") == slug:
                    record["guideReport"] = guide_block
                    record.setdefault("links", {})["guideReport"] = rel_path
                    changed = True
                    break
            if changed:
                feed_path.write_text(
                    json.dumps(feed, indent=2) + "\n", encoding="utf-8"
                )

        return self._send_json({"status": "ok", "slug": slug, "guideReport": guide_block}, 200)

    def _handle_project_files(self, slug: str):
        """Return a recursive file listing for a generated project."""
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        files = []
        for file_path in sorted(project_root.rglob("*")):
            if not file_path.is_file():
                continue
            if ".git" in file_path.parts:
                continue
            relative = file_path.relative_to(project_root).as_posix()
            files.append(
                {
                    "path": relative,
                    "size": file_path.stat().st_size,
                    "previewable": file_path.suffix.lower() in TEXT_PREVIEW_SUFFIXES,
                }
            )

        return self._send_json({"project": slug, "files": files}, 200)

    def _handle_project_file_preview(self, slug: str, query: str):
        """Return a text preview for a project file."""
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        relative_path = (parse_qs(query).get("path") or [""])[0]
        if not relative_path:
            return self._send_json({"error": "Missing path query parameter"}, 400)

        requested_path = (project_root / relative_path).resolve()
        if project_root not in requested_path.parents or not requested_path.is_file():
            return self._send_json({"error": "File not found"}, 404)

        if requested_path.suffix.lower() not in TEXT_PREVIEW_SUFFIXES:
            return self._send_json({"error": "File type is not previewable"}, 415)

        if requested_path.stat().st_size > MAX_PREVIEW_BYTES:
            return self._send_json({"error": f"File too large to preview (max {MAX_PREVIEW_BYTES} bytes)"}, 413)

        try:
            content = requested_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._send_json({"error": "Preview supports UTF-8 text files only"}, 415)

        return self._send_json(
            {
                "project": slug,
                "path": requested_path.relative_to(project_root).as_posix(),
                "content": content,
            },
            200,
        )

    def _handle_project_download(self, slug: str):
        """Stream a ZIP archive for a generated project."""
        project_root = self._resolve_project_root(slug)
        if not project_root:
            return self._send_json({"error": "Project not found"}, 404)

        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(project_root.rglob("*")):
                if file_path.is_file():
                    if ".git" in file_path.parts:
                        continue
                    archive.write(file_path, arcname=f"{slug}/{file_path.relative_to(project_root).as_posix()}")

        payload = archive_buffer.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{slug}.zip"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        return

    def _handle_project_analysis(self, slug):
        """Generate and serve analysis for a project by slug."""
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"
        
        if not feed_path.exists():
            return self._send_json({"error": "Project feed not found"}, 404)
        
        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
            projects = feed.get("projects", [])
            project = next((p for p in projects if p.get("slug") == slug), None)
            
            if not project:
                return self._send_json({"error": f"Project '{slug}' not found"}, 404)
            
            # Generate analysis from project metadata
            analysis = self._generate_project_analysis(project)
            return self._send_json(analysis, 200)
        except json.JSONDecodeError:
            return self._send_json({"error": "Invalid project feed"}, 500)

    def _generate_project_analysis(self, project):
        """Generate analysis content for a project from its metadata."""
        title = project.get("title", project.get("slug", "Unknown"))
        generated_from = project.get("generatedFrom", "Unknown BRD")
        status = project.get("status", "Unknown")
        
        # Build generic analysis based on project metadata
        analysis = {
            "title": title,
            "projectSlug": project.get("slug", ""),
            "generatedFrom": generated_from,
            "designChoice": f"Generated from: {generated_from}",
            "benefits": [
                "Automated architecture generation from business requirements",
                "Consistent application of Azure best practices",
                "Infrastructure as Code generated and validated",
            ],
            "alternativeConsidered": "Manual architecture design (rejected for time and consistency)",
            "status": status,
        }
        
        return analysis

    def _handle_project_operations(self, slug):
        """Generate and serve operations/monitoring view for a project by slug."""
        feed_path = FACTORY_REPO_ROOT / "factory-projects.generated.json"

        if not feed_path.exists():
            return self._send_json({"error": "Project feed not found"}, 404)

        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
            projects = feed.get("projects", [])
            project = next((p for p in projects if p.get("slug") == slug), None)

            if not project:
                return self._send_json({"error": f"Project '{slug}' not found"}, 404)

            operations = self._generate_project_operations(project)
            return self._send_json(operations, 200)
        except json.JSONDecodeError:
            return self._send_json({"error": "Invalid project feed"}, 500)

    def _generate_project_operations(self, project):
        """Generate operations metadata for portal display."""
        enable_observability = bool((project.get("options") or {}).get("enableObservability", False))
        network_tier = _sanitize_network_tier((project.get("options") or {}).get("networkTier", "public"))
        network_tier_label = {
            "public": "Public (internet-facing)",
            "vnet-integrated": "VNet-integrated (NSG + subnet delegation)",
            "private": "Private (internal LB + private endpoints)",
        }.get(network_tier, network_tier)
        monitoring_resources = [
            "Log Analytics Workspace",
            "Application Insights (workspace-based)",
            "Optional Azure Monitor Action Group",
        ] if enable_observability else [
            "No monitoring resources requested during intake",
        ]

        checklist = [
            "Deploy infra/main.bicep and capture deployment outputs",
            "Wire app telemetry to APPINSIGHTS_CONNECTION_STRING",
            "Validate /health endpoint and request traces",
            "Assign operations owner and alert routing",
        ] if enable_observability else [
            "Decide whether to enable observability for this project",
            "Add Application Insights and Log Analytics before production",
            "Define alert routing and operational ownership",
        ]

        return {
            "projectSlug": project.get("slug", ""),
            "title": project.get("title", project.get("slug", "Unknown")),
            "enableObservability": enable_observability,
            "networkTier": network_tier,
            "networkTierLabel": network_tier_label,
            "monitoringResources": monitoring_resources,
            "checklist": checklist,
            "links": project.get("links", {}),
        }

    def _handle_application_zone_packs(self):
        """Return Application Zone offerings, including App Packs and Agent Packs."""
        packs = _portal_build_pack_catalog()
        agent_packs = _portal_build_agent_pack_catalog()
        return self._send_json({
            "updated_at": _utcnow_iso(),
            "packs": packs,
            "agentPacks": agent_packs,
            "offerings": (
                [dict(item, offeringType="app-pack") for item in packs]
                + agent_packs
            ),
        }, 200)

    def _handle_application_zone_pack_versions(self, pack_id: str):
        """Return available versions for a given App Pack."""
        versions = _portal_list_pack_versions(pack_id)
        if not versions:
            return self._send_json({"error": f"App pack not found: {pack_id}"}, 404)
        return self._send_json({
            "packId": pack_id,
            "versions": [(item.get("metadata") or {}).get("version") for item in versions],
        }, 200)

    def _handle_application_zone_pack_manifest(self, pack_id: str, version: str):
        """Return one App Pack manifest."""
        pack = _portal_get_pack_or_none(pack_id, version)
        if not pack:
            return self._send_json(
                {"error": f"App pack version not found: {pack_id}@{version}"},
                404,
            )
        return self._send_json(pack, 200)

    def _handle_aapaas_summary(self):
        """Return AAPAAS instance, health, scheduler, and certification evidence."""
        instances = _portal_load_aapaas_instances()
        health = _portal_load_aapaas_health()
        scheduler = _portal_load_aapaas_scheduler_report()
        certifications = list(_portal_load_aapaas_certifications().values())
        agent_packs = _portal_build_agent_pack_catalog()
        healthy_instances = [
            instance for instance in instances
            if str(instance.get("healthStatus", "")).lower() in {"passed", "healthy"}
        ]
        return self._send_json({
            "updated_at": _utcnow_iso(),
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
                "schedulerStatus": (scheduler.get("syncResult") or {}).get("status"),
            },
        }, 200)

    def _handle_security_control_tower_work_board(self):
        """Return the Security Control Tower Red/Blue/Green work board."""
        return self._send_json(_portal_load_security_work_board(), 200)

    def _handle_security_control_tower_tool_integrations(self):
        """Return safe read-only and draft-only tool integration contracts."""
        return self._send_json(_portal_load_security_tool_integrations(), 200)

    def _handle_security_control_tower_approval_workflows(self):
        """Return named-human approval workflows for sensitive actions."""
        return self._send_json(_portal_load_security_approval_workflows(), 200)

    def _handle_security_control_tower_pilot_readiness(self):
        """Return production-pilot readiness gates for Security Control Tower."""
        return self._send_json(_portal_load_security_pilot_readiness(), 200)

    def _handle_security_control_tower_connector_pilot(self):
        """Return live connector pilot preparation contracts for Security Control Tower."""
        return self._send_json(_portal_load_security_connector_pilot(), 200)

    def _handle_security_control_tower_pilot_evidence(self):
        """Return production-pilot evidence capture plan for Security Control Tower."""
        return self._send_json(_portal_load_security_pilot_evidence(), 200)

    def _handle_application_zone_validate_inputs(self):
        """Validate a Quick Launch payload against the selected App Pack manifest."""
        payload, ok = _portal_parse_json_payload(self)
        if not ok:
            return
        result = _portal_validate_app_pack_inputs(payload or {})
        return self._send_json(result, 200 if result.get("valid") else 400)

    def _handle_application_zone_create_instance(self):
        """Create a portal-side Application Zone instance for runtime testing."""
        payload, ok = _portal_parse_json_payload(self)
        if not ok:
            return
        validation = _portal_validate_app_pack_inputs(payload or {})
        if not validation.get("valid"):
            return self._send_json(validation, 400)

        pack_info = validation.get("pack") or {}
        inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
        env_name = str(inputs.get("environmentName", "") or "appzone").strip()
        safe_env = re.sub(r"[^a-zA-Z0-9-]+", "-", env_name).strip("-").lower() or "appzone"
        instance_id = f"{safe_env}-{pack_info.get('packId', 'pack')}-{uuid.uuid4().hex[:8]}"
        runtime = inputs.get("runtime") if isinstance(inputs.get("runtime"), dict) else {}
        instance = {
            "instanceId": instance_id,
            "displayName": f"{pack_info.get('displayName', pack_info.get('packId', 'App Pack'))} ({env_name})",
            "status": "ready-for-runtime",
            "profile": str(payload.get("profile", "dev") or "dev"),
            "createdAt": _utcnow_iso(),
            "pack": pack_info,
            "inputs": inputs,
            "runtime": dict(runtime),
        }
        APPLICATION_ZONE_RUNTIME_INSTANCES[instance_id] = instance
        return self._send_json({
            "ok": True,
            "mode": "portal-runtime-workspace",
            "message": "Instance workspace created. Connect a runtime URL to invoke live agents.",
            "instance": _portal_summarize_instance(instance),
        }, 201)

    def _handle_application_zone_instance_action(self, instance_id: str, action_path: str):
        """Handle runtime connection, discovery, and proxy actions for a portal instance."""
        instance = APPLICATION_ZONE_RUNTIME_INSTANCES.get(instance_id)
        if not instance:
            return self._send_json({"error": f"Application Zone instance not found: {instance_id}"}, 404)

        action_path = (action_path or "").strip("/")
        if action_path == "connect-runtime":
            payload, ok = _portal_parse_json_payload(self)
            if not ok:
                return
            base_url = str((payload or {}).get("baseUrl", "") or "").strip().rstrip("/")
            if not base_url:
                return self._send_json({"error": "baseUrl is required"}, 400)
            if not re.match(r"^https?://", base_url):
                return self._send_json({"error": "baseUrl must start with http:// or https://"}, 400)
            runtime = {"baseUrl": base_url}
            api_key = str((payload or {}).get("apiKey", "") or "").strip()
            if api_key:
                runtime["apiKey"] = api_key
            instance["runtime"] = runtime
            return self._send_json({
                "ok": True,
                "instance": _portal_summarize_instance(instance),
            }, 200)

        if action_path == "agents":
            pack = _portal_get_pack_or_none(
                str((instance.get("pack") or {}).get("packId", "")),
                str((instance.get("pack") or {}).get("version", "")),
            ) or {}
            return self._send_json({
                "ok": True,
                "connected": bool((instance.get("runtime") or {}).get("baseUrl")),
                "instance": _portal_summarize_instance(instance),
                "agents": pack.get("agents", []),
                "services": pack.get("services", []),
            }, 200)

        if action_path.startswith("agents/") and action_path.endswith("/invoke"):
            parts = action_path.split("/")
            agent_id = parts[1] if len(parts) >= 3 else ""
            payload, ok = _portal_parse_json_payload(self)
            if not ok:
                return
            pack = _portal_get_pack_or_none(
                str((instance.get("pack") or {}).get("packId", "")),
                str((instance.get("pack") or {}).get("version", "")),
            ) or {}
            agents = pack.get("agents", [])
            agent = next((item for item in agents if item.get("agentId") == agent_id), None)
            if not agent:
                return self._send_json({"error": f"Agent not found: {agent_id}"}, 404)
            endpoint = ((payload or {}).get("endpoint") or (agent.get("endpoints") or {}).get("query") or "").strip()
            method = str((payload or {}).get("method") or "POST").upper()
            body = (payload or {}).get("body")
            return self._proxy_application_zone_runtime(instance, endpoint, method, body)

        if action_path == "invoke":
            payload, ok = _portal_parse_json_payload(self)
            if not ok:
                return
            endpoint = str((payload or {}).get("path", "") or "").strip()
            method = str((payload or {}).get("method", "POST") or "POST").upper()
            body = (payload or {}).get("body")
            return self._proxy_application_zone_runtime(instance, endpoint, method, body)

        if action_path == "casewright/chat-query":
            payload, ok = _portal_parse_json_payload(self)
            if not ok:
                return
            return self._proxy_application_zone_runtime(instance, "/api/chat/query", "POST", payload)

        return self._send_json({"error": "Invalid Application Zone instance action"}, 400)

    def _proxy_application_zone_runtime(self, instance: dict, endpoint: str, method: str, body):
        runtime = instance.get("runtime") or {}
        base_url = str(runtime.get("baseUrl", "") or "").strip().rstrip("/")
        if not base_url:
            return self._send_json({"error": "Runtime is not connected. Use Connect Runtime first."}, 400)
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        headers = {}
        if runtime.get("apiKey"):
            headers["x-api-key"] = str(runtime["apiKey"])
        data, error = _http_json_request(
            base_url + endpoint,
            method=method,
            headers=headers,
            payload=body if isinstance(body, dict) else {},
        )
        if error:
            return self._send_json({
                "ok": False,
                "runtimeBaseUrl": base_url,
                "endpoint": endpoint,
                "error": error,
            }, 502)
        return self._send_json({
            "ok": True,
            "runtimeBaseUrl": base_url,
            "endpoint": endpoint,
            "response": data,
        }, 200)

    def _send_json(self, payload, status=200):
        """Send JSON response"""
        response = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _handle_health(self):
        """Lightweight liveness probe with no external dependency checks."""
        uptime_seconds = int(max(0, time.time() - SERVICE_START_EPOCH))
        return self._send_json(
            {
                "status": "ok",
                "service": "azure-architecture-factory-portal",
                "probe": "liveness",
                "timeUtc": _utcnow_iso(),
                "uptimeSeconds": uptime_seconds,
            },
            200,
        )

    def _handle_ready(self):
        """Readiness probe verifying portal can actually serve intake traffic.

        Critical checks (gate 503):
          - portalHtml: factory-portal.html is present
          - projectsDir: projects/ directory exists
          - intakeDirWritable: docs/intake/ can be written + deleted

        Informational (reported but do not gate):
          - otelEnabled: OpenTelemetry exporter initialized
          - rateLimiterActive: always True when reached (proves module loaded)
          - blobStorage: cached HEAD probe against container when BLOB_ENABLED
        """
        portal_file = FACTORY_REPO_ROOT / "factory-portal.html"
        projects_dir = FACTORY_REPO_ROOT / "projects"
        intake_dir = FACTORY_REPO_ROOT / "docs" / "intake"

        checks: dict = {
            "portalHtml": portal_file.is_file(),
            "projectsDir": projects_dir.is_dir(),
            "intakeDirWritable": _probe_intake_writable(intake_dir),
        }
        critical_ok = all(checks.values())

        info: dict = {
            "otelEnabled": _otel_enabled(),
            "rateLimiterActive": _INTAKE_LIMITER is not None,
        }
        if blob_sync.BLOB_ENABLED:
            info["blobStorage"] = _probe_blob_storage_cached()

        ready = critical_ok
        status = 200 if ready else 503
        return self._send_json(
            {
                "status": "ready" if ready else "not_ready",
                "service": "azure-architecture-factory-portal",
                "probe": "readiness",
                "timeUtc": _utcnow_iso(),
                "checks": checks,
                "info": info,
            },
            status,
        )

    def _handle_resilience_metrics(self):
        """Return circuit breaker and resilience executor metrics.
        
        Exposes:
        - BRD processor executor: retry attempts, successes, failures, circuit state
        - Circuit breaker: state (open/closed/half-open), failure count, recovery info
        """
        metrics = {
            "service": "azure-architecture-factory-portal",
            "probe": "resilience",
            "timeUtc": _utcnow_iso(),
            "brdProcessor": _BRD_EXECUTOR.get_metrics(),
        }
        return self._send_json(metrics, 200)

    # Extensions/paths the browser can safely cache for a few seconds.
    # Short max-age lets F5 inside the window serve from memory-cache instantly
    # without a conditional request, while still picking up edits within ~10s.
    _STATIC_CACHE_EXTS = (".html", ".css", ".js", ".svg", ".png", ".jpg",
                          ".jpeg", ".gif", ".ico", ".woff", ".woff2")

    def _is_static_cacheable(self) -> bool:
        try:
            path = urlparse(self.path).path.lower()
        except Exception:
            return False
        if path.startswith("/api/") or path.startswith("/.auth/"):
            return False
        return path.endswith(self._STATIC_CACHE_EXTS)

    def end_headers(self):
        """Add CORS headers to all responses"""
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Factory-Api-Key, Authorization")
        self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self._is_static_cacheable():
            # Short, must-revalidate window so rapid reloads are instant but
            # real edits are picked up on the next poll.
            self.send_header("Cache-Control", "private, max-age=10, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        """Custom logging"""
        logger.info("%s - %s" % (self.client_address[0], format % args))


def main():
    # Pull persisted state (projects, feed, owners) from blob storage before
    # serving any traffic. No-op when FACTORY_PORTAL_BLOB_ACCOUNT is unset.
    if blob_sync.BLOB_ENABLED:
        try:
            summary = blob_sync.sync_down(FACTORY_REPO_ROOT)
            logger.info("Blob sync-down summary: %s", summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Blob sync-down failed: %s", exc)

    # Initialize OpenTelemetry / Azure Monitor. Safe no-op when deps are not
    # installed or APPLICATIONINSIGHTS_CONNECTION_STRING is not set.
    if init_otel(service_name="aaf-portal", service_version=os.environ.get("AAFACTORY_VERSION", "dev")):
        logger.info("OpenTelemetry initialized (Azure Monitor exporter active)")
    else:
        logger.info("OpenTelemetry not initialized (no connection string or deps missing)")

    # ThreadingHTTPServer handles concurrent HTTP requests instead of serializing
    # them. Previously a single slow request blocked every other client on the
    # TCP accept loop; this is particularly visible under burst load or when
    # several users poll status at once.
    _restore_runs_on_startup()
    _start_watchdog()
    httpd = ThreadingHTTPServer((BIND_ADDRESS, PORT), FactoryPortalHandler)
    httpd.daemon_threads = True
    httpd.allow_reuse_address = True
    display_host = "localhost" if BIND_ADDRESS in {"0.0.0.0", "::"} else BIND_ADDRESS

    print("\n" + "=" * 80)
    print("AZURE ARCHITECTURE FACTORY - DEDICATED PORTAL")
    print("=" * 80)
    print(f"\nFactory Portal:     http://{display_host}:{PORT}/factory-portal.html")
    print(f"Friendly Alias:     http://{display_host}:{PORT}/portal")
    print(f"BRD Intake API:     http://{display_host}:{PORT}/api/brd-intake")
    print(f"CSA Companion API:  {CSA_COPILOT_API_BASE or '(not configured)'}")
    print(f"Project Directory:  http://{BIND_ADDRESS}:{PORT}/projects/")
    if display_host != BIND_ADDRESS:
        print(f"Listening On:       http://{BIND_ADDRESS}:{PORT} (all interfaces)")
    if _jwks_cache:
        print(f"Auth:               Entra ID (tenant={ENTRA_TENANT_ID}, client={ENTRA_CLIENT_ID})")
    elif os.environ.get(API_KEY_ENV, "").strip():
        print("Auth:               Master API key + issued HMAC tokens (usage-counted)")
        print(f"Token Admin:        POST http://{display_host}:{PORT}/api/admin/issue-token")
        print(f"Token Usage:        GET  http://{display_host}:{PORT}/api/admin/tokens")
    else:
        print("Auth:               None (local dev mode)")
    print("\nYou can now:")
    print("  • Submit BRDs via the portal")
    print("  • View generated projects in real-time")
    print("  • Monitor pipeline execution status")
    print("  • Access project documentation and architecture")
    print("\nTip: Press Ctrl+C to stop the server.")
    print("=" * 80 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
