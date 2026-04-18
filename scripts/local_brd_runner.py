from __future__ import annotations

import base64
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    # Local sibling module.
    from .generate_guide_report import generate_guide_report  # type: ignore
except ImportError:  # pragma: no cover - executed as a script
    from generate_guide_report import generate_guide_report  # type: ignore

try:
    from factory_runtime import classify_brd as _classify_brd  # type: ignore
except ImportError:  # pragma: no cover - executed as a script
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from factory_runtime import classify_brd as _classify_brd  # type: ignore


def process_brd_document(
    factory_repo_root: Path,
    brd_path: Path,
    run_id: str,
    generation_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brd_text = brd_path.read_text(encoding="utf-8")
    generation_options = generation_options or {}
    enable_observability = bool(generation_options.get("enableObservability", True))
    _VALID_NETWORK_TIERS = {"public", "vnet-integrated", "private"}
    network_tier = str(generation_options.get("networkTier", "public")).strip().lower()
    if network_tier not in _VALID_NETWORK_TIERS:
        network_tier = "public"
    generated_at = datetime.now(timezone.utc)
    generated_at_iso = generated_at.isoformat().replace("+00:00", "Z")
    timestamp = generated_at.strftime("%Y%m%d%H%M%S")

    title = _extract_title(brd_text, brd_path.stem)
    requirements = _extract_requirements(brd_text)
    success_criteria = _extract_success_criteria(brd_text)
    capabilities = _infer_capabilities(brd_text)
    runtime_recommendation = _classify_runtime(brd_text)
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
            "Monitoring and observability starter guidance is included by request." if enable_observability else "Monitoring and observability wiring can be added during refinement.",
        ],
        "alternativeConsidered": "Shelling out to a sibling repository pipeline was rejected because it is not portable to the hosted Azure deployment.",
        "status": "Ready",
        "generationOptions": {
            "enableObservability": enable_observability,
            "networkTier": network_tier,
        },
    }

    _write_text(project_root / "README.md", _build_readme(title, brd_path.name, slug, requirements, enable_observability))
    _write_text(project_root / "DEPLOY.md", _build_deploy(slug, enable_observability))
    _write_text(docs_dir / "architecture-overview.md", _build_architecture_overview(title, requirements, capabilities, enable_observability, network_tier))
    _write_text(docs_dir / "governance-model.md", _build_governance_model(capabilities, enable_observability))
    _write_text(docs_dir / "delivery-milestones.md", _build_delivery_milestones(enable_observability))
    _write_text(docs_dir / "success-criteria.md", _build_success_criteria(success_criteria))
    _write_text(docs_dir / "traceability-matrix.md", _build_traceability_matrix(requirements, success_criteria))
    _write_text(diagrams_dir / diagram_notes_basename, _build_diagram_notes(title, requirements, capabilities, enable_observability, network_tier))
    _write_text(diagrams_dir / diagram_basename, _build_drawio(title, network_tier, capabilities))
    _write_text(src_dir / "__init__.py", "")
    _write_text(src_dir / "main.py", _build_api_main())
    _write_text(src_dir / "models.py", _build_api_models())
    _write_text(services_dir / "__init__.py", "")
    _write_text(services_dir / "copilot_service.py", _build_api_service())
    _write_text(project_root / "requirements.txt", "fastapi==0.116.1\nuvicorn[standard]==0.32.1\npydantic==2.10.3\n")
    _write_text(project_root / "pyproject.toml", _build_pyproject(title))
    _write_text(infra_dir / "main.bicep", _build_infra_bicep(enable_observability, network_tier))
    _write_text(tests_dir / "test_generated_project.py", _build_test())

    # Copy the shared model-selector script template into every generated project
    # so users have a one-command way to switch Azure OpenAI deployments with
    # cost and trade-off context.
    scripts_dir = project_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    _template_root = Path(__file__).resolve().parent / "templates"
    _select_model_src = _template_root / "select_model.ps1"
    if _select_model_src.exists():
        shutil.copyfile(_select_model_src, scripts_dir / "select_model.ps1")

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
        "suggested_runtime": runtime_recommendation,
        "generation_options": {
            "enableObservability": enable_observability,
            "networkTier": network_tier,
        },
        "user_home_copy": str(user_home_copy_path),
    }
    _write_json(project_root / "project-manifest.json", manifest)

    # Generate the deterministic guide report (heuristic, no LLM) so portal-only
    # users can view workflow-guide output without running Copilot locally.
    guide_report_info: dict[str, Any] = {}
    try:
        guide_report_info = generate_guide_report(project_root, brd_path)
    except Exception as exc:  # pragma: no cover - defensive: never fail the run
        guide_report_info = {"error": str(exc)}
    if guide_report_info.get("report_path"):
        manifest["guide_report"] = {
            "path": _repo_relative(
                factory_repo_root, Path(guide_report_info["report_path"])
            ),
            "generated_at": guide_report_info.get("generated_at"),
            "severity_counts": guide_report_info.get("severity_counts", {}),
        }
        project_links["guideReport"] = manifest["guide_report"]["path"]
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
        f"enable_observability={str(enable_observability).lower()}",
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
        "options": {
            "enableObservability": enable_observability,
            "networkTier": network_tier,
        },
        "links": project_links,
        "runLog": f"outputs\\brd-runs\\{run_log_name}",
        "suggestedRuntime": runtime_recommendation,
    }
    if manifest.get("guide_report"):
        project_record["guideReport"] = manifest["guide_report"]
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


def _classify_runtime(markdown: str) -> dict[str, Any]:
    """Ask the factory runtime classifier which agent runtime to recommend.

    Non-breaking: wrapped in a try/except so a classifier bug can never
    fail a factory run. Returns a small dict safe to embed in the
    project manifest and feed.
    """

    try:
        result = _classify_brd(markdown)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "runtime": "local",
            "source": "error-fallback",
            "error": str(exc),
        }
    return {
        "runtime": result.runtime,
        "source": result.source,
        "score": result.score,
        "signals": result.signals,
        "counterSignals": result.counter_signals,
        "reasoning": result.reasoning,
    }


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


def _build_readme(title: str, source_brd: str, slug: str, requirements: list[str], enable_observability: bool) -> str:
    highlights = "\n".join(f"- {item}" for item in requirements[:10])
    observability_line = "- Monitoring and observability wiring requested: Yes" if enable_observability else "- Monitoring and observability wiring requested: No"
    return f"# {title}\n\nGenerated from BRD `{source_brd}` by the Azure-native factory runner.\n\n## What Was Generated\n- `docs/architecture-overview.md`\n- `docs/governance-model.md`\n- `docs/delivery-milestones.md`\n- `docs/success-criteria.md`\n- `docs/traceability-matrix.md`\n- `diagrams/{slug}.md`\n- `diagrams/{slug}.drawio`\n- `src/copilot_api/main.py`\n- `src/copilot_api/models.py`\n- `src/copilot_api/services/copilot_service.py`\n- `requirements.txt`\n- `infra/main.bicep`\n- `tests/test_generated_project.py`\n\n## Selected Generation Options\n{observability_line}\n\n## BRD Requirement Highlights\n{highlights}\n"


def _build_deploy(slug: str, enable_observability: bool) -> str:
    deployment_steps = [
        "1. Review and customize `infra/main.bicep`.",
        "2. Provision hosting, identity, Key Vault access, and Application Insights.",
        "3. Configure application settings for the generated API.",
        f"4. Deploy the project from `projects/{slug}`.",
        "5. Validate `/health` after deployment.",
    ]
    if enable_observability:
        deployment_steps[1] = "2. Provision hosting, identity, Key Vault access, Application Insights, and Log Analytics."
        deployment_steps.insert(3, "4. Configure health probes, alerts, dashboards, and operational ownership for the generated workload.")
        deployment_steps[4] = f"5. Deploy the project from `projects/{slug}`."
        deployment_steps[5] = "6. Validate `/health` after deployment and confirm telemetry reaches Azure Monitor."
    return "# Deploy\n\n## Prerequisites\n- Python 3.11+\n- Azure CLI authenticated\n- Target Azure subscription and resource group\n\n## Local Validation\n```bash\npython -m venv .venv\n.venv\\Scripts\\activate\npython -m pip install -r requirements.txt\npython -m pytest tests -q\n```\n\n## Local Run\n```bash\npython -m uvicorn src.copilot_api.main:app --host 127.0.0.1 --port 8000 --reload\n```\n\n## Azure Deployment Outline\n" + "\n".join(deployment_steps) + "\n"


def _build_architecture_overview(title: str, requirements: list[str], capabilities: dict[str, bool], enable_observability: bool, network_tier: str = "public") -> str:
    capability_lines = [
        f"- Azure OpenAI: {'Yes' if capabilities['openai'] else 'Not explicitly requested'}",
        f"- Microsoft Copilot: {'Yes' if capabilities['copilot'] else 'Not explicitly requested'}",
        f"- Machine Learning lifecycle: {'Yes' if capabilities['ml'] else 'Not explicitly requested'}",
        f"- Governance controls: {'Yes' if capabilities['governance'] else 'Baseline included'}",
    ]
    requirement_lines = "\n".join(f"- {item}" for item in requirements[:8])
    building_blocks = [
        "- Presentation or workflow entry point",
        "- Integration API layer",
        "- Data or document store",
        "- Observability with Application Insights and Log Analytics",
        "- Identity, secrets, and governance controls",
    ]
    if enable_observability:
        building_blocks.insert(4, "- Azure Monitor alerts, dashboards, and health probes")
    network_section = {
        "public": "- **Network Tier**: Public (internet-facing, no VNet isolation)",
        "vnet-integrated": (
            "- **Network Tier**: VNet-integrated\n"
            "  - Azure Virtual Network with dedicated application subnet\n"
            "  - Network Security Group with default-deny inbound rule\n"
            "  - Subnet delegation for Azure Container Apps environment\n"
            "  - Extend with private endpoints for Key Vault, Storage, and databases"
        ),
        "private": (
            "- **Network Tier**: Private (no public ingress)\n"
            "  - Azure Virtual Network with application and private endpoint subnets\n"
            "  - NSG with default-deny inbound; internal load balancer only\n"
            "  - Private endpoints for downstream Azure services\n"
            "  - Requires VPN Gateway or ExpressRoute for developer access"
        ),
    }.get(network_tier, f"- **Network Tier**: {network_tier}")
    return (
        f"# {title} - Architecture Overview\n\n"
        "## Target Architecture\n"
        "This starter architecture packages the submitted BRD into a generated project scaffold that can be refined for Azure deployment.\n\n"
        f"## Requirement Signals\n{requirement_lines}\n\n"
        "## Recommended Building Blocks\n" + "\n".join(building_blocks) + "\n\n"
        f"## Network Topology\n{network_section}\n\n"
        "## Capability Coverage\n" + "\n".join(capability_lines) + "\n"
    )


def _build_governance_model(capabilities: dict[str, bool], enable_observability: bool) -> str:
    controls = [
        "- Managed identity for service-to-service authentication",
        "- Key Vault-backed secret management",
        "- Least-privilege RBAC for runtime and deployment identities",
        "- Application Insights and structured run logs for traceability",
    ]
    if enable_observability:
        controls.append("- Log Analytics workspace, health probes, and alert routing are part of the starter operating model")
    if capabilities["governance"]:
        controls.append("- Governance review checkpoint based on BRD security and compliance requirements")
    return "# AI/ML Governance Model\n\n## Governance Controls\n" + "\n".join(controls) + "\n\n## Operating Cadence\n- Review generated starter assets before production use\n- Track deployment changes through version control and manifest updates\n- Re-run BRD generation when requirements materially change\n"


def _build_delivery_milestones(enable_observability: bool) -> str:
    lines = [
        "# Delivery Milestones",
        "",
        "## Phase 1 - Intake and Architecture",
        "- Capture BRD inputs",
        "- Generate baseline project artifacts and architecture notes",
        "",
        "## Phase 2 - Application Refinement",
        "- Replace starter API implementation with workload-specific logic",
        "- Expand tests, infrastructure, and deployment automation",
        "",
        "## Phase 3 - Production Readiness",
        "- Harden security, networking, and observability",
        "- Validate deployment readiness and operational ownership",
    ]
    if enable_observability:
        lines.insert(-1, "- Wire Application Insights, Log Analytics, alerts, and dashboard ownership")
    return "\n".join(lines) + "\n"


def _build_success_criteria(success_criteria: list[str]) -> str:
    lines = "\n".join(f"- {item}" for item in success_criteria)
    return f"# Success Criteria\n\n## KPI Candidates\n{lines}\n\n## Measurement Approach\n- Establish a baseline before implementation\n- Track changes through test results, deployment validation, and user feedback\n- Assign an owner for each acceptance criterion\n"


def _build_traceability_matrix(requirements: list[str], success_criteria: list[str]) -> str:
    _ARTIFACT_MAP: list[tuple[set[str], str]] = [
        ({"api", "endpoint", "rest", "integration", "connect", "webhook", "http"},
         "Starter API — `src/copilot_api/main.py`"),
        ({"auth", "identity", "rbac", "managed", "secret", "key vault", "security", "access", "permission"},
         "Bicep infra — `infra/main.bicep` (Identity & RBAC)"),
        ({"observ", "monitor", "log", "metric", "alert", "insight", "telemetry", "trace", "dashboard"},
         "Architecture overview — `docs/architecture-overview.md`"),
        ({"deploy", "pipeline", "ci", "cd", "release", "container", "docker", "image"},
         "Deployment guide — `docs/deploy.md`"),
        ({"govern", "policy", "compliance", "audit", "review", "soc", "iso", "regulation"},
         "Governance model — `docs/governance-model.md`"),
        ({"test", "validat", "verif", "quality", "acceptance", "criteria"},
         "Test scaffold — `tests/test_generated_project.py`"),
        ({"data", "store", "database", "persist", "storage", "blob", "queue", "cosmos"},
         "Architecture overview + extend Bicep for data resources"),
        ({"architect", "design", "service", "component", "module", "layer", "diagram"},
         "Architecture diagram — `diagrams/<slug>.md`"),
    ]

    def _infer_artifacts(req_text: str) -> str:
        lower = req_text.lower()
        matched = [artifact for keywords, artifact in _ARTIFACT_MAP if any(kw in lower for kw in keywords)]
        if not matched:
            matched = ["Architecture overview — `docs/architecture-overview.md`",
                       "Starter API — `src/copilot_api/main.py`"]
        return "; ".join(matched[:2])

    def _infer_status(req_text: str) -> str:
        lower = req_text.lower()
        if any(kw in lower for kw in {"data", "database", "persist", "workflow", "approval",
                                       "external", "machine learning", "ml", "train", "stream"}):
            return "Pending Extension"
        if any(kw in lower for kw in {"govern", "policy", "compliance", "audit", "soc", "iso",
                                       "regulation", "certif"}):
            return "Review Required"
        return "Scaffolded"

    rows = [
        "| ID | BRD Requirement | Generated Artifact(s) | Status | Validation Approach |",
        "|---|---|---|---|---|",
    ]
    req_statuses: list[str] = []
    for i, req in enumerate(requirements[:15], start=1):
        req_id = f"REQ-{i:03d}"
        status = _infer_status(req)
        req_statuses.append(status)
        validation = (
            "Extend generated tests; link test case to this requirement"
            if status == "Pending Extension"
            else "Assign acceptance owner; verify generated artifact covers intent"
        )
        rows.append(
            f"| {req_id} | {req.replace('|', '/')} | {_infer_artifacts(req)} | {status} | {validation} |"
        )
    for i, criterion in enumerate(success_criteria[:6], start=1):
        rows.append(
            f"| SC-{i:03d} | **Success:** {criterion.replace('|', '/')} "
            f"| Success criteria — `docs/success-criteria.md` | Review Required "
            f"| Assign owner; establish baseline metric before go-live |"
        )

    total = len(req_statuses)
    scaffolded = req_statuses.count("Scaffolded")
    pending = req_statuses.count("Pending Extension")
    review = req_statuses.count("Review Required")
    pct = lambda n: f"{round(n / total * 100)}%" if total else "0%"

    summary = (
        "\n\n## Coverage Summary\n\n"
        "| Status | Count | Share |\n|---|---|---|\n"
        f"| ✅ Scaffolded | {scaffolded} | {pct(scaffolded)} |\n"
        f"| 🔧 Pending Extension | {pending} | {pct(pending)} |\n"
        f"| 🔍 Review Required | {review} | {pct(review)} |\n\n"
        "> **Next step**: Invoke the `project-traceability-advisor` agent to produce a full\n"
        "> requirement → code → test → infrastructure coverage report and update `project-manifest.json`.\n"
    )
    return "# Traceability Matrix\n\n" + "\n".join(rows) + summary


def _build_diagram_notes(title: str, requirements: list[str], capabilities: dict[str, bool], enable_observability: bool, network_tier: str = "public") -> str:
    capability_lines = [f"- {name}: {'yes' if enabled else 'no'}" for name, enabled in capabilities.items()]
    capability_lines.append(f"- observability_wiring: {'yes' if enable_observability else 'no'}")
    capability_lines.append(f"- network_tier: {network_tier}")
    return f"# {title} - Architecture Overview\n\n## Summary\nThis generated starter design maps the BRD into a simple Azure-oriented architecture shape.\n\n## Signals\n" + "\n".join(f"- {item}" for item in requirements[:8]) + "\n\n## Capability Flags\n" + "\n".join(capability_lines) + "\n"


def _svg_data_uri(icon_path: Path) -> str:
    svg_bytes = icon_path.read_bytes()
    encoded = base64.b64encode(svg_bytes).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


# Azure service color palette: fill_color → used for node backgrounds
_SVC_PALETTE: dict[str, str] = {
    "identity": "#0078D4",  # Azure Blue       — Managed Identity / Entra ID
    "api":      "#E66A00",  # Orange            — API Management
    "compute":  "#7719AA",  # Purple            — Functions / Container Apps
    "logic":    "#0066CC",  # Blue              — Logic Apps
    "ai":       "#00689D",  # Teal              — OpenAI / AI / ML
    "observa":  "#682D63",  # Plum              — App Insights / Monitor
    "security": "#A80000",  # Dark Red          — Key Vault / Governance
    "network":  "#107C10",  # Green             — Virtual Network
    "data":     "#004B87",  # Dark Blue         — Cosmos DB / Data Store
}


# Capability → label + color-key mapping for _build_drawio
_CAP_ICONS: dict[str, dict[str, str]] = {
    # node1: user / identity entry point — always Managed Identities
    "entry": {
        "default_label": "Managed Identity\n/ Users",
        "default_color": "identity",
    },
    # node2: API gateway — prefer API Management when api capability is set
    "api": {
        "yes_label":     "API Management",
        "yes_color":     "api",
        "default_label": "API Service\n(Container Apps)",
        "default_color": "compute",
    },
    # node3: business logic / processing
    "logic": {
        "workflow_label": "Workflow\n/ Logic Apps",
        "workflow_color": "logic",
        "copilot_label":  "Copilot Service\n(Container Apps)",
        "copilot_color":  "compute",
        "default_label":  "Processing\n/ Azure Functions",
        "default_color":  "compute",
    },
    # node4: AI / data intelligence
    "ai_data": {
        "openai_label":  "Azure OpenAI\n/ AI Foundry",
        "openai_color":  "ai",
        "copilot_label": "AI / Cognitive\nServices",
        "copilot_color": "ai",
        "ml_label":      "Azure Machine\nLearning",
        "ml_color":      "ai",
        "default_label": "Data Store\n/ Cosmos DB",
        "default_color": "data",
    },
    # node5: observability — App Insights if wired, else Monitor
    "observability": {
        "yes_label":     "Application\nInsights",
        "yes_color":     "observa",
        "default_label": "Azure Monitor",
        "default_color": "observa",
    },
    # node6 (optional): governance / security
    "governance": {
        "yes_label": "Key Vault\n/ Governance",
        "yes_color": "security",
    },
    # node7 (optional): network isolation
    "network": {
        "private_label": "VNet\n+ Private Endpoints",
        "vnet_label":    "VNet + NSG",
        "color":         "network",
    },
}


# Render all generated architecture nodes with Azure icon images only.
_AZURE_ICON_BY_COLOR_KEY: dict[str, str] = {
    "identity": "managed-identities.svg",
    "api": "api-management.svg",
    "compute": "managed-identities.svg",
    "logic": "api-management.svg",
    "ai": "monitor.svg",
    "observa": "monitor.svg",
    "security": "managed-identities.svg",
    "network": "virtual-networks.svg",
    "data": "storage-accounts.svg",
}


def _azure_icon_data_uri(icon_file: str) -> str:
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "azure-icons" / icon_file
    return _svg_data_uri(icon_path)


def _build_drawio(title: str, network_tier: str = "public", capabilities: dict[str, bool] | None = None) -> str:
    """Generate a capability-aware architecture diagram using Azure icon nodes only."""
    caps = capabilities or {}
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _cell(cid: str, label: str, color_key: str, x: int, y: int, w: int = 220, h: int = 100) -> str:
        safe_label = (
            label
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "&#xa;")
        )
        bg = _SVC_PALETTE.get(color_key, "#0078D4")
        icon_file = _AZURE_ICON_BY_COLOR_KEY.get(color_key, "managed-identities.svg")
        icon_data_uri = _azure_icon_data_uri(icon_file)
        style = (
            "shape=image;imageAspect=0;aspect=fixed;"
            f"image={icon_data_uri};"
            f"fillColor={bg};strokeColor=#0f172a;fontColor=#0f172a;"
            "labelBackgroundColor=#ffffff;labelBorderColor=#dbe2ea;"
            "labelPosition=center;verticalLabelPosition=bottom;verticalAlign=top;align=center;"
            "spacingTop=4;spacing=8;whiteSpace=wrap;html=1;fontSize=12;fontStyle=1;"
        )
        return (
            f'<mxCell id="{cid}" value="{safe_label}" '
            f'style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
            f'</mxCell>'
        )

    def _edge(eid: str, src: str, tgt: str, color: str = "#2a6ea8") -> str:
        return (
            f'<mxCell id="{eid}" value="" '
            f'style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={color};endArrow=block;endFill=1;" '
            f'edge="1" parent="1" source="{src}" target="{tgt}">'
            f'<mxGeometry relative="1" as="geometry"/>'
            f'</mxCell>'
        )

    # ── Row 1: main flow (y=220) ──────────────────────────────────────────────
    # node1: entry / identity
    n1_color = _CAP_ICONS["entry"]["default_color"]
    n1_label = _CAP_ICONS["entry"]["default_label"]

    # node2: API layer
    if caps.get("api"):
        n2_color, n2_label = _CAP_ICONS["api"]["yes_color"], _CAP_ICONS["api"]["yes_label"]
    else:
        n2_color, n2_label = _CAP_ICONS["api"]["default_color"], _CAP_ICONS["api"]["default_label"]

    # node3: business logic
    if caps.get("workflow"):
        n3_color, n3_label = _CAP_ICONS["logic"]["workflow_color"], _CAP_ICONS["logic"]["workflow_label"]
    elif caps.get("copilot"):
        n3_color, n3_label = _CAP_ICONS["logic"]["copilot_color"], _CAP_ICONS["logic"]["copilot_label"]
    else:
        n3_color, n3_label = _CAP_ICONS["logic"]["default_color"], _CAP_ICONS["logic"]["default_label"]

    # node4: AI / data
    if caps.get("openai"):
        n4_color, n4_label = _CAP_ICONS["ai_data"]["openai_color"], _CAP_ICONS["ai_data"]["openai_label"]
    elif caps.get("copilot"):
        n4_color, n4_label = _CAP_ICONS["ai_data"]["copilot_color"], _CAP_ICONS["ai_data"]["copilot_label"]
    elif caps.get("ml"):
        n4_color, n4_label = _CAP_ICONS["ai_data"]["ml_color"], _CAP_ICONS["ai_data"]["ml_label"]
    else:
        n4_color, n4_label = _CAP_ICONS["ai_data"]["default_color"], _CAP_ICONS["ai_data"]["default_label"]

    # node5: observability
    if caps.get("observability_wiring"):
        n5_color, n5_label = _CAP_ICONS["observability"]["yes_color"], _CAP_ICONS["observability"]["yes_label"]
    else:
        n5_color, n5_label = _CAP_ICONS["observability"]["default_color"], _CAP_ICONS["observability"]["default_label"]

    cells = [
        _cell("node1", n1_label, n1_color,  80,  220),
        _cell("node2", n2_label, n2_color,  380, 220),
        _cell("node3", n3_label, n3_color,  680, 220),
        _cell("node4", n4_label, n4_color,  980, 220),
        _cell("node5", n5_label, n5_color, 1280, 220, w=240),
    ]
    edges = [
        _edge("edge1", "node1", "node2"),
        _edge("edge2", "node2", "node3"),
        _edge("edge3", "node3", "node4"),
        _edge("edge4", "node4", "node5"),
    ]

    # ── Row 2: optional supporting services (y=420) ──────────────────────────
    row2_x = 380
    row2_node_id = 6

    if caps.get("governance"):
        g_color = _CAP_ICONS["governance"]["yes_color"]
        g_label = _CAP_ICONS["governance"]["yes_label"]
        cells.append(_cell(f"node{row2_node_id}", g_label, g_color, row2_x, 420))
        edges.append(_edge(f"edge{row2_node_id}", "node2", f"node{row2_node_id}", "#7b1fa2"))
        row2_x += 300
        row2_node_id += 1

    if network_tier in ("vnet-integrated", "private"):
        vnet_label = (
            _CAP_ICONS["network"]["private_label"]
            if network_tier == "private"
            else _CAP_ICONS["network"]["vnet_label"]
        )
        vnet_color = _CAP_ICONS["network"]["color"]
        cells.append(_cell(f"node{row2_node_id}", vnet_label, vnet_color, row2_x, 420))
        edges.append(_edge(f"edge{row2_node_id}", "node2", f"node{row2_node_id}", "#2e7d32"))

    nodes_xml = "".join(cells)
    edges_xml = "".join(edges)
    return (
        f'<mxfile host="app.diagrams.net" version="24.7.3">'
        f'<diagram id="arch1" name="Architecture">'
        f'<mxGraphModel dx="1600" dy="900" grid="1" gridSize="10" guides="1" tooltips="1"'
        f' connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1680"'
        f' pageHeight="1100" math="0" shadow="0">'
        f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'<mxCell id="title" value="{safe_title}" style="text;html=1;strokeColor=none;fillColor=none;'
        f'align=left;verticalAlign=middle;fontSize=24;fontStyle=1;" vertex="1" parent="1">'
        f'<mxGeometry x="80" y="60" width="1500" height="40" as="geometry"/></mxCell>'
        f'{nodes_xml}'
        f'{edges_xml}'
        f'</root></mxGraphModel></diagram></mxfile>'
    )


def _build_api_main() -> str:
    return "from datetime import datetime, timezone\nfrom fastapi import FastAPI\n\nfrom .models import AskRequest, AskResponse\nfrom .services.copilot_service import build_response\n\n\napp = FastAPI(title=\"Generated Copilot API\", version=\"0.1.0\")\n\n\n@app.get(\"/health\")\ndef health() -> dict:\n    return {\"status\": \"ok\", \"timestamp\": datetime.now(timezone.utc).isoformat()}\n\n\n@app.post(\"/api/copilot/ask\", response_model=AskResponse)\ndef ask_copilot(payload: AskRequest) -> AskResponse:\n    return AskResponse(answer=build_response(payload.question, payload.context), source=\"generated-starter\")\n"


def _build_api_models() -> str:
    return "from pydantic import BaseModel, Field\n\n\nclass AskRequest(BaseModel):\n    question: str = Field(min_length=3)\n    context: str = Field(default=\"\")\n\n\nclass AskResponse(BaseModel):\n    answer: str\n    source: str\n"


def _build_api_service() -> str:
    return "def build_response(question: str, context: str) -> str:\n    summary = context.strip()[:240]\n    if summary:\n        return \"Starter copilot response for question: '\" + question + \"'. Context summary: \" + summary + \". Replace this logic with your workload-specific orchestration.\"\n    return \"Starter copilot response for question: '\" + question + \"'. Replace this logic with your workload-specific orchestration.\"\n"


def _build_pyproject(title: str) -> str:
    normalized = _slugify(title).replace("-", "_")
    return f"[project]\nname = \"{normalized}\"\nversion = \"0.1.0\"\ndescription = \"Generated starter project for {title}\"\nrequires-python = \">=3.11\"\ndependencies = [\n  \"fastapi==0.116.1\",\n  \"uvicorn[standard]==0.32.1\",\n  \"pydantic==2.10.3\",\n]\n"


def _build_infra_bicep(enable_observability: bool, network_tier: str = "public") -> str:
    enable_obs_default = "true" if enable_observability else "false"

    params = (
        "targetScope = 'resourceGroup'\n\n"
        "@description('Deployment location')\n"
        "param location string = resourceGroup().location\n\n"
        "@description('Environment name')\n"
        "param environment string = 'dev'\n\n"
        "@description('Logical workload name used in generated resource names')\n"
        "param workloadName string = 'starter-workload'\n\n"
        "@description('Whether the starter should include monitoring and observability resources')\n"
        f"param enableObservability bool = {enable_obs_default}\n\n"
        "@description('Optional operations email for alert notifications. Leave empty to skip email actions.')\n"
        "param operationsEmail string = ''\n"
    )

    if network_tier == "vnet-integrated":
        params += (
            "\n@description('Address prefix for the virtual network')\n"
            "param vnetAddressPrefix string = '10.0.0.0/16'\n\n"
            "@description('Address prefix for the application subnet')\n"
            "param appSubnetPrefix string = '10.0.0.0/24'\n"
        )
    elif network_tier == "private":
        params += (
            "\n@description('Address prefix for the virtual network')\n"
            "param vnetAddressPrefix string = '10.0.0.0/16'\n\n"
            "@description('Address prefix for the application subnet')\n"
            "param appSubnetPrefix string = '10.0.0.0/24'\n\n"
            "@description('Address prefix for the private endpoint subnet')\n"
            "param peSubnetPrefix string = '10.0.1.0/24'\n"
        )

    base = params + "\n\nvar resourceBaseName = toLower(replace('${workloadName}-${environment}', '_', '-'))\n"

    if network_tier in ("vnet-integrated", "private"):
        subnets = (
            "      {\n"
            "        name: 'app-subnet'\n"
            "        properties: {\n"
            "          addressPrefix: appSubnetPrefix\n"
            "          networkSecurityGroup: { id: nsg.id }\n"
            "          delegations: [\n"
            "            {\n"
            "              name: 'app-env-delegation'\n"
            "              properties: { serviceName: 'Microsoft.App/environments' }\n"
            "            }\n"
            "          ]\n"
            "        }\n"
            "      }\n"
        )
        if network_tier == "private":
            subnets += (
                "      {\n"
                "        name: 'pe-subnet'\n"
                "        properties: {\n"
                "          addressPrefix: peSubnetPrefix\n"
                "          privateEndpointNetworkPolicies: 'Disabled'\n"
                "        }\n"
                "      }\n"
            )

        base += (
            "\nresource nsg 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {\n"
            "  name: '${resourceBaseName}-nsg'\n"
            "  location: location\n"
            "  properties: {\n"
            "    securityRules: [\n"
            "      {\n"
            "        name: 'deny-inbound-default'\n"
            "        properties: {\n"
            "          priority: 4000\n"
            "          direction: 'Inbound'\n"
            "          access: 'Deny'\n"
            "          protocol: '*'\n"
            "          sourcePortRange: '*'\n"
            "          destinationPortRange: '*'\n"
            "          sourceAddressPrefix: '*'\n"
            "          destinationAddressPrefix: '*'\n"
            "        }\n"
            "      }\n"
            "    ]\n"
            "  }\n"
            "}\n"
            "\nresource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' = {\n"
            "  name: '${resourceBaseName}-vnet'\n"
            "  location: location\n"
            "  properties: {\n"
            "    addressSpace: { addressPrefixes: [ vnetAddressPrefix ] }\n"
            f"    subnets: [\n{subnets}"
            "    ]\n"
            "  }\n"
            "  dependsOn: [ nsg ]\n"
            "}\n"
        )

    base += (
        "\nresource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = if (enableObservability) {\n"
        "  name: '${resourceBaseName}-law'\n"
        "  location: location\n"
        "  properties: {\n"
        "    retentionInDays: 30\n"
        "    features: {\n"
        "      enableLogAccessUsingOnlyResourcePermissions: true\n"
        "    }\n"
        "  }\n"
        "  sku: {\n"
        "    name: 'PerGB2018'\n"
        "  }\n"
        "}\n\n"
        "resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = if (enableObservability) {\n"
        "  name: '${resourceBaseName}-appi'\n"
        "  location: location\n"
        "  kind: 'web'\n"
        "  properties: {\n"
        "    Application_Type: 'web'\n"
        "    WorkspaceResourceId: logAnalyticsWorkspace.id\n"
        "    IngestionMode: 'LogAnalytics'\n"
        "  }\n"
        "}\n\n"
        "resource operationsActionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (enableObservability && !empty(operationsEmail)) {\n"
        "  name: '${resourceBaseName}-opsag'\n"
        "  location: 'global'\n"
        "  properties: {\n"
        "    enabled: true\n"
        "    groupShortName: 'opsalert'\n"
        "    emailReceivers: [\n"
        "      {\n"
        "        name: 'operations-team'\n"
        "        emailAddress: operationsEmail\n"
        "        useCommonAlertSchema: true\n"
        "      }\n"
        "    ]\n"
        "  }\n"
        "}\n"
        "\noutput deploymentHint string = 'Replace this starter Bicep file with workload-specific Azure resources.'\n"
        "output locationUsed string = location\n"
        "output environmentName string = environment\n"
        "output observabilityEnabled bool = enableObservability\n"
        "output logAnalyticsWorkspaceName string = enableObservability ? logAnalyticsWorkspace.name : 'not-enabled'\n"
        "output appInsightsName string = enableObservability ? applicationInsights.name : 'not-enabled'\n"
        "output appInsightsConnectionString string = enableObservability ? applicationInsights.properties.ConnectionString : ''\n"
        "output actionGroupName string = (enableObservability && !empty(operationsEmail)) ? operationsActionGroup.name : 'not-configured'\n"
    )

    if network_tier in ("vnet-integrated", "private"):
        base += "output vnetName string = vnet.name\n"
        base += "output appSubnetId string = vnet.properties.subnets[0].id\n"
    if network_tier == "private":
        base += "output peSubnetId string = vnet.properties.subnets[1].id\n"

    return base


def _build_test() -> str:
    return "from pathlib import Path\n\n\ndef test_generated_project_docs_exist():\n    root = Path(__file__).resolve().parents[1]\n    required = [\n        root / 'README.md',\n        root / 'DEPLOY.md',\n        root / 'requirements.txt',\n        root / 'src' / 'copilot_api' / 'main.py',\n        root / 'src' / 'copilot_api' / 'models.py',\n        root / 'src' / 'copilot_api' / 'services' / 'copilot_service.py',\n        root / 'docs' / 'architecture-overview.md',\n        root / 'docs' / 'governance-model.md',\n        root / 'docs' / 'delivery-milestones.md',\n        root / 'docs' / 'success-criteria.md',\n        root / 'docs' / 'traceability-matrix.md',\n        root / 'diagrams' / (root.name + '.md'),\n        root / 'project-manifest.json',\n    ]\n    missing = [str(path) for path in required if not path.exists()]\n    assert not missing, f'Missing generated docs: {missing}'\n"