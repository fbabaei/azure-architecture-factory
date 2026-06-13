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
    from factory_runtime import assess_brd_readiness as _assess_brd_readiness  # type: ignore
    from factory_runtime import classify_brd as _classify_brd  # type: ignore
except ImportError:  # pragma: no cover - executed as a script
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from factory_runtime import assess_brd_readiness as _assess_brd_readiness  # type: ignore
    from factory_runtime import classify_brd as _classify_brd  # type: ignore

try:
    from . import language_agents, iac_agents  # type: ignore
    from .iac_agents.azd_emitter import AzdEmitter, AzdEmitContext  # type: ignore
except ImportError:  # pragma: no cover - executed as a script
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    import language_agents  # type: ignore
    import iac_agents  # type: ignore
    from iac_agents.azd_emitter import AzdEmitter, AzdEmitContext  # type: ignore


def _normalize_target_slug(value: object) -> str | None:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", candidate):
        raise ValueError("targetProjectSlug contains invalid characters")
    return candidate


def _snapshot_existing_project(factory_repo_root: Path, slug: str, project_root: Path, generated_at: datetime) -> Path:
    history_root = factory_repo_root / "projects" / "_history" / slug
    history_root.mkdir(parents=True, exist_ok=True)
    snapshot_path = history_root / generated_at.strftime("%Y%m%d%H%M%S")
    if snapshot_path.exists():
        shutil.rmtree(snapshot_path)
    shutil.copytree(project_root, snapshot_path)
    return snapshot_path


def process_brd_document(
    factory_repo_root: Path,
    brd_path: Path,
    run_id: str,
    generation_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brd_text = brd_path.read_text(encoding="utf-8")
    generation_options = generation_options or {}
    enable_observability = bool(generation_options.get("enableObservability", True))
    # Infra and security are ON by default. Portal / CLI can opt OUT via
    # generateInfra=false or runSecurityAudit=false to produce a docs-only or
    # audit-skipped project. Both flags propagate into the manifest so the
    # orchestrator's Phase 3 (infra validation) and Phase 2.6 (security gate)
    # can skip cleanly without re-reading the original portal payload.
    generate_infra = bool(generation_options.get("generateInfra", True))
    run_security_audit = bool(generation_options.get("runSecurityAudit", True))
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
    archetype = _detect_archetype(requirements, brd_text)
    runtime_recommendation = _classify_runtime(brd_text)
    readiness_assessment = _assess_readiness(brd_text)
    auto_flow_gate = _build_auto_flow_gate(readiness_assessment)
    language_agent = language_agents.resolve_from_brd(brd_text)
    iac_agent = iac_agents.resolve_from_brd(brd_text)
    # Portal / caller override: generation_options can force a specific
    # language or IaC tool, bypassing BRD markdown inference. Unknown
    # values fall back to the default agent (handled by `.get()`).
    language_override = str(generation_options.get("implementationLanguage") or "").strip().lower()
    if language_override:
        language_agent = language_agents.get(language_override)
    iac_override = str(generation_options.get("iacTool") or "").strip().lower()
    if iac_override:
        iac_agent = iac_agents.get(iac_override)
    target_slug = _normalize_target_slug(generation_options.get("targetProjectSlug"))
    update_snapshot_path: Path | None = None
    if target_slug:
        slug = target_slug
        project_root = factory_repo_root / "projects" / slug
        manifest_path = project_root / "project-manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"Project slug '{slug}' was not found")
        update_snapshot_path = _snapshot_existing_project(factory_repo_root, slug, project_root, generated_at)
        shutil.rmtree(project_root)
    else:
        base_slug = f"{_slugify(title)}-{timestamp}"
        # Collision guard: two BRD runs within the same second must not overwrite
        # each other. If the target folder already exists, append a short suffix
        # derived from the run_id (stable across the same run, unique across runs).
        slug = base_slug
        if (factory_repo_root / "projects" / slug).exists():
            suffix = (run_id or "").replace("-", "")[-6:] or generated_at.strftime("%f")[:6]
            slug = f"{base_slug}-{suffix}"
            # Paranoia: if that ALSO exists, walk a counter until we find a free slot.
            counter = 1
            while (factory_repo_root / "projects" / slug).exists():
                slug = f"{base_slug}-{suffix}-{counter}"
                counter += 1

        project_root = factory_repo_root / "projects" / slug
    diagrams_dir = project_root / "diagrams"
    docs_dir = project_root / "docs"
    tests_dir = project_root / "tests"
    infra_dir = project_root / "infra"
    logs_dir = project_root / "logs"
    outputs_dir = factory_repo_root / "outputs" / "brd-runs"

    _base_dirs = [diagrams_dir, docs_dir, tests_dir, logs_dir, outputs_dir]
    if generate_infra:
        _base_dirs.append(infra_dir)
    for path in _base_dirs:
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
        "sourceType": str(generation_options.get("sourceType") or "brd-markdown"),
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
            "generateInfra": generate_infra,
            "runSecurityAudit": run_security_audit,
        },
        "implementationLanguage": language_agent.name,
        "iacTool": iac_agent.name if generate_infra else "disabled",
        "archetype": archetype,
        "brdReadiness": readiness_assessment,
        "orchestratorAutoFlow": auto_flow_gate,
    }
    if update_snapshot_path is not None:
        analysis["updateTargetProject"] = slug
        analysis["updateSnapshot"] = _repo_relative(factory_repo_root, update_snapshot_path)

    _write_text(docs_dir / "architecture-overview.md", _build_architecture_overview(title, requirements, capabilities, enable_observability, network_tier, generate_infra))
    _write_text(docs_dir / "governance-model.md", _build_governance_model(capabilities, enable_observability))
    _write_text(docs_dir / "delivery-milestones.md", _build_delivery_milestones(enable_observability))
    _write_text(docs_dir / "success-criteria.md", _build_success_criteria(success_criteria))
    _write_text(diagrams_dir / diagram_notes_basename, _build_diagram_notes(title, requirements, capabilities, enable_observability, network_tier))
    _write_text(diagrams_dir / diagram_basename, _build_drawio(title, network_tier, capabilities))

    # Delegate language-specific source code to the language specialist.
    language_result = language_agent.emit(
        language_agents.LanguageEmitContext(
            project_root=project_root,
            tests_dir=tests_dir,
            title=title,
            slug=slug,
            source_brd=brd_path.name,
            requirements=requirements,
            enable_observability=enable_observability,
            archetype=archetype,
        )
    )

    # Traceability matrix references the language agent's actual primary
    # source path (e.g. src/mdr_support/main.py, src/Program.cs) so the
    # "Starter API" row in generated docs always points at a real file.
    _write_text(
        docs_dir / "traceability-matrix.md",
        _build_traceability_matrix(requirements, success_criteria, language_result.primary_source_path),
    )

    # Delegate infrastructure emission to the IaC specialist — unless the
    # caller opted out via generation_options.generateInfra=false. Skipping
    # leaves infra_dir unwritten and records iac_files=[] + iac_tool="disabled"
    # so the orchestrator's Phase 3 skips cleanly without trying to validate
    # a missing folder.
    if generate_infra:
        iac_result = iac_agent.emit(
            iac_agents.IacEmitContext(
                infra_dir=infra_dir,
                title=title,
                slug=slug,
                enable_observability=enable_observability,
                network_tier=network_tier,
                language=language_agent.name,
            )
        )
        iac_files_written: list[str] = iac_result.files_written
        iac_tool_recorded = iac_agent.name
    else:
        iac_files_written = []
        iac_tool_recorded = "disabled"

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
        "source_type": str(generation_options.get("sourceType") or "brd-markdown"),
        "source_file_name": str(generation_options.get("sourceFileName") or brd_path.name),
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
            "generateInfra": generate_infra,
            "runSecurityAudit": run_security_audit,
        },
        "implementation_language": language_agent.name,
        "iac_tool": iac_tool_recorded,
        "archetype": archetype,
        "brd_readiness": readiness_assessment,
        "orchestrator_auto_flow": auto_flow_gate,
        "language_files": language_result.files_written,
        "iac_files": iac_files_written,
        "user_home_copy": str(user_home_copy_path),
    }
    if generation_options.get("sourceAttachment"):
        manifest["source_attachment"] = str(generation_options["sourceAttachment"])
    if update_snapshot_path is not None:
        manifest["update"] = {
            "mode": "replace-in-place",
            "target_project": slug,
            "snapshot": _repo_relative(factory_repo_root, update_snapshot_path),
        }
    _write_json(project_root / "project-manifest.json", manifest)

    # azd adapter emission. Bicep stays the source of truth; when a Bicep infra
    # was emitted we also write `azure.yaml` + `infra/main.parameters.json` so
    # the project is `azd up`-ready out of the box. The emitter parses the
    # just-written main.bicep, so the parameters always mirror the real params.
    # Opt out with generation_options.generateAzd=false.
    generate_azd = bool(generation_options.get("generateAzd", True))
    azd_files_written: list[str] = []
    if generate_infra and iac_tool_recorded == "bicep" and generate_azd:
        try:
            azd_result = AzdEmitter().emit(
                AzdEmitContext(project_root=project_root, manifest=manifest, slug=slug)
            )
            azd_files_written = azd_result.files_written
            manifest["azd_files"] = azd_files_written
            _write_json(project_root / "project-manifest.json", manifest)
        except Exception as exc:  # pragma: no cover - never fail the run on azd
            manifest["azd_error"] = str(exc)


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
        "status": "Ready" if auto_flow_gate.get("eligible") else "Ready (Architect Review Required)",
        "generatedFrom": brd_path.name,
        "sourceType": str(generation_options.get("sourceType") or "brd-markdown"),
        "generatedAt": generated_at_iso,
        "options": {
            "enableObservability": enable_observability,
            "networkTier": network_tier,
            "generateInfra": generate_infra,
            "runSecurityAudit": run_security_audit,
        },
        "links": project_links,
        "runLog": f"outputs\\brd-runs\\{run_log_name}",
        "suggestedRuntime": runtime_recommendation,
        "brdReadiness": readiness_assessment,
        "orchestratorAutoFlow": auto_flow_gate,
        "implementationLanguage": language_agent.name,
        "iacTool": iac_tool_recorded,
    }
    if update_snapshot_path is not None:
        project_record["update"] = {
            "mode": "replace-in-place",
            "snapshot": _repo_relative(factory_repo_root, update_snapshot_path),
        }
    if manifest.get("guide_report"):
        project_record["guideReport"] = manifest["guide_report"]
    _update_project_feed(factory_repo_root / "factory-projects.generated.json", generated_at_iso, project_record)

    return {
        "status": "complete",
        "project": project_record,
        "brdReadiness": readiness_assessment,
        "orchestratorAutoFlow": auto_flow_gate,
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


def _assess_readiness(markdown: str) -> dict[str, Any]:
    """Run deterministic BRD readiness assessment with safe fallback."""

    try:
        result = _assess_brd_readiness(markdown)
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "classification": "Auto-Ready With Guardrails",
            "percentage_score": 0,
            "blockers": [f"readiness-evaluation-error: {exc}"],
            "guardrails": ["BRD readiness evaluation failed; require architect review before orchestration."],
            "clarification_questions": [
                "Please provide a clearer BRD with workload, data, integrations, security, and environment details."
            ],
        }
    return result.to_dict()


def _build_auto_flow_gate(readiness: dict[str, Any]) -> dict[str, Any]:
    """Determine whether project-orchestrator runtime:auto should proceed."""

    classification = str(readiness.get("classification") or "")
    eligible = classification != "Architect Review Required"
    gate_reason = (
        "BRD readiness gate passed for runtime:auto orchestration."
        if eligible
        else "BRD readiness is Architect Review Required; block runtime:auto and require pre-review clarification."
    )
    return {
        "mode": "auto",
        "eligible": eligible,
        "classification": classification,
        "reason": gate_reason,
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


# Archetype detection: maps BRD keyword signals to a workload shape so the
# Python language agent can emit domain-appropriate scaffolding instead of a
# generic single-endpoint stub. Detection is deterministic and keyword-based
# so the same BRD always produces the same archetype.
#
#   extraction-chat - document ingestion + structured extraction + interactive
#                     clarification loop + human-in-the-loop chat. Matches
#                     workloads like MDR arrangement creation, insurance
#                     claim intake, KYC, tax form filling.
#   rag-qa          - Q&A / retrieval over a corpus (policy lookup, customer
#                     support knowledge base).
#   api-service     - default fallback: a generic REST API stub.
_EXTRACTION_CHAT_SIGNALS = (
    "extract", "extraction", "ingest", "ingestion",
    "document upload", "upload", "unstructured",
    "clarif",  # clarification, clarifying
    "arrangement", "draft", "draft generation",
    "form filling", "form-filling", "form fill",
    "human-in-the-loop", "human in the loop",
    "chat experience", "interactive chat", "chat flow",
    "json format", "structured data",
    "pdf", "mandatory field",
)
_RAG_QA_SIGNALS = (
    "q&a", "qa ", "question and answer", "questions and answers",
    "retrieve", "retrieval", "knowledge base", "vector search",
    "policy lookup", "customer support", "search corpus",
    "rag",
)


def _detect_archetype(requirements: list[str], markdown: str) -> str:
    """Pick the best-fit workload archetype from BRD text.

    Counts distinct keyword matches across requirements + full BRD body and
    picks the archetype with the most hits (minimum 2). Ties break toward
    ``extraction-chat`` because its scaffolding is a superset of ``rag-qa``
    (upload + extract is a strict richer shape than Q&A alone).
    """

    text = (markdown + "\n" + "\n".join(requirements)).lower()
    extraction_hits = sum(1 for sig in _EXTRACTION_CHAT_SIGNALS if sig in text)
    rag_hits = sum(1 for sig in _RAG_QA_SIGNALS if sig in text)
    if extraction_hits >= 2 and extraction_hits >= rag_hits:
        return "extraction-chat"
    if rag_hits >= 2:
        return "rag-qa"
    return "api-service"


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


def _build_architecture_overview(title: str, requirements: list[str], capabilities: dict[str, bool], enable_observability: bool, network_tier: str = "public", generate_infra: bool = True) -> str:
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
    infra_section = (
        "Infrastructure-as-Code artifacts are emitted under `infra/`."
        if generate_infra
        else (
            "Infrastructure-as-Code generation was **opted out** for this run (`generateInfra=false`). "
            "The `infra/` folder is intentionally absent; Phase 3 (infra validation) and Phase 5 (deployment) "
            "are skipped. Re-run the BRD with the *Generate Azure infrastructure* option enabled to produce "
            "deployable Bicep or Terraform."
        )
    )
    return (
        f"# {title} - Architecture Overview\n\n"
        "## Target Architecture\n"
        "This starter architecture packages the submitted BRD into a generated project scaffold that can be refined for Azure deployment.\n\n"
        f"## Requirement Signals\n{requirement_lines}\n\n"
        "## Recommended Building Blocks\n" + "\n".join(building_blocks) + "\n\n"
        f"## Network Topology\n{network_section}\n\n"
        f"## Infrastructure-as-Code\n{infra_section}\n\n"
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


def _build_traceability_matrix(
    requirements: list[str],
    success_criteria: list[str],
    primary_source_path: str = "src/copilot_api/main.py",
) -> str:
    starter_api = f"Starter API — `{primary_source_path}`"
    _ARTIFACT_MAP: list[tuple[set[str], str]] = [
        ({"api", "endpoint", "rest", "integration", "connect", "webhook", "http"},
         starter_api),
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
                       starter_api]
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

