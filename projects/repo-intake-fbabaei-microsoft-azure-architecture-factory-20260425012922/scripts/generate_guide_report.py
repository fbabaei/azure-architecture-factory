"""Generate a deterministic ``docs/guide-report.md`` for a factory project.

This is the Python equivalent of the ``factory-workflow-guide`` Copilot agent
for portal-only users who cannot run Copilot locally. It produces a heuristic,
no-LLM report based on on-disk artefacts plus the BRD text. The report is
written into ``projects/<slug>/docs/guide-report.md`` and the caller is
expected to record the generation timestamp in ``project-manifest.json``.

The script is safe to run standalone:

    python scripts/generate_guide_report.py projects/<slug>

It intentionally avoids any external dependencies so it works inside the
portal container and at BRD-generation time.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class GuideFinding:
    severity: str  # "critical" | "warning" | "advisory" | "ok"
    title: str
    detail: str
    paths: list[str] = field(default_factory=list)


def generate_guide_report(project_root: Path, brd_path: Path | None = None) -> dict:
    """Analyse a project folder and write ``docs/guide-report.md``.

    Returns a metadata dict with ``generated_at`` (ISO8601 UTC) and
    ``report_path`` (relative to the factory repo root if possible).
    """
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise FileNotFoundError(f"Project folder not found: {project_root}")

    manifest = _read_manifest(project_root)
    brd_text = _read_brd(brd_path, manifest)
    findings = _collect_findings(project_root, manifest, brd_text)
    next_steps = _derive_next_steps(findings, manifest)

    generated_at = datetime.now(timezone.utc)
    generated_at_iso = generated_at.isoformat().replace("+00:00", "Z")

    report_md = _render_report(
        project_root=project_root,
        manifest=manifest,
        findings=findings,
        next_steps=next_steps,
        generated_at_iso=generated_at_iso,
    )

    docs_dir = project_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / "guide-report.md"
    report_path.write_text(report_md, encoding="utf-8")

    return {
        "generated_at": generated_at_iso,
        "report_path": str(report_path),
        "severity_counts": _severity_counts(findings),
    }


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def _read_manifest(project_root: Path) -> dict:
    manifest_path = project_root / "project-manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _read_brd(brd_path: Path | None, manifest: dict) -> str:
    candidates: list[Path] = []
    if brd_path:
        candidates.append(Path(brd_path))
    source = manifest.get("source_brd")
    if source:
        candidates.append(Path(source))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def _collect_findings(
    project_root: Path,
    manifest: dict,
    brd_text: str,
) -> list[GuideFinding]:
    findings: list[GuideFinding] = []
    opts = manifest.get("generation_options", {}) or {}
    network_tier = str(opts.get("networkTier", "public")).lower()
    observability = bool(opts.get("enableObservability", False))
    brd_lower = brd_text.lower()

    # --- Option/BRD mismatches ---------------------------------------------
    wants_private = any(
        phrase in brd_lower
        for phrase in (
            "private endpoint",
            "private vnet",
            "no public internet",
            "no public exposure",
            "isolated network",
            "vnet integration",
            "private link",
        )
    )
    if wants_private and network_tier == "public":
        findings.append(
            GuideFinding(
                severity="critical",
                title="Network tier is public but BRD requires private networking",
                detail=(
                    "The BRD mentions private endpoints / no public exposure, but "
                    "`generation_options.networkTier` is `public`. Regenerate with "
                    "`networkTier: private` so the starter Bicep includes VNet, "
                    "private endpoints, and NSGs."
                ),
                paths=["project-manifest.json", "infra/main.bicep"],
            )
        )

    wants_observability = any(
        phrase in brd_lower
        for phrase in (
            "application insights",
            "distributed tracing",
            "observability",
            "monitoring",
            "slo",
            "sla",
            "alerting",
            "telemetry",
        )
    )
    if wants_observability and not observability:
        findings.append(
            GuideFinding(
                severity="critical",
                title="Observability disabled but BRD requires telemetry / SLOs / alerts",
                detail=(
                    "`generation_options.enableObservability` is false, so no "
                    "Application Insights / Log Analytics / Action Group resources "
                    "were emitted. Regenerate with `enableObservability: true`."
                ),
                paths=["project-manifest.json", "infra/main.bicep"],
            )
        )

    # --- Placeholder Bicep --------------------------------------------------
    bicep_path = project_root / "infra" / "main.bicep"
    if bicep_path.is_file():
        bicep_text = bicep_path.read_text(encoding="utf-8", errors="ignore")
        is_placeholder = (
            "Replace this starter Bicep" in bicep_text
            or len(bicep_text.splitlines()) < 120
        )
        modules_dir = project_root / "infra" / "modules"
        has_modules = modules_dir.is_dir() and any(modules_dir.iterdir())
        if is_placeholder and not has_modules:
            findings.append(
                GuideFinding(
                    severity="critical",
                    title="infra/main.bicep is a starter placeholder, not a real implementation",
                    detail=(
                        "The Bicep file is a scaffold and `infra/modules/` is empty. "
                        "Run `azure-architecture-implementer` to emit per-service "
                        "Bicep modules that match the diagram."
                    ),
                    paths=["infra/main.bicep", "infra/modules/"],
                )
            )

    # --- Phase gaps ---------------------------------------------------------
    phase_log = project_root / "logs" / "phase-3-infra-validation.log"
    if not phase_log.is_file():
        findings.append(
            GuideFinding(
                severity="critical",
                title="Bicep validation (Phase 3) has not run",
                detail=(
                    "No `logs/phase-3-infra-validation.log` exists. Run the "
                    "`bicep-infrastructure-validator` agent before deploying."
                ),
                paths=["logs/phase-3-infra-validation.log"],
            )
        )
    production_checklist = project_root / "docs" / "production-checklist.md"
    if not production_checklist.is_file():
        findings.append(
            GuideFinding(
                severity="critical",
                title="Production readiness review (Phase 4) has not run",
                detail=(
                    "No `docs/production-checklist.md` exists. Run the "
                    "`production-environment-advisor` agent to confirm production "
                    "gates (identity, secrets, networking, monitoring, RBAC)."
                ),
                paths=["docs/production-checklist.md"],
            )
        )

    # --- Manifest status drift ---------------------------------------------
    status = str(manifest.get("status", "")).lower()
    if status == "complete" and (
        not phase_log.is_file() or not production_checklist.is_file()
    ):
        findings.append(
            GuideFinding(
                severity="warning",
                title="Manifest says status=complete but phases 3 and 4 are missing",
                detail=(
                    "Reset `status` in `project-manifest.json` to `in-progress` "
                    "until validation and production review complete."
                ),
                paths=["project-manifest.json"],
            )
        )

    # --- Services vs diagram components ------------------------------------
    src_dir = project_root / "src"
    service_dirs = (
        [p for p in src_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
        if src_dir.is_dir()
        else []
    )
    if len(service_dirs) <= 1:
        findings.append(
            GuideFinding(
                severity="warning",
                title="Only starter service scaffold exists under src/",
                detail=(
                    "The starter runner emits one `copilot_api` service. If your "
                    "diagram lists multiple services, run "
                    "`azure-architecture-implementer` to scaffold each component."
                ),
                paths=["src/"],
            )
        )

    # --- Stale home copy ---------------------------------------------------
    home_copy = manifest.get("user_home_copy")
    if home_copy:
        findings.append(
            GuideFinding(
                severity="advisory",
                title="A duplicate copy exists under your user home",
                detail=(
                    f"`{home_copy}` was created by the starter runner. It will "
                    "drift from the workspace copy after regeneration. Treat the "
                    "workspace project as the source of truth."
                ),
                paths=[home_copy],
            )
        )

    # --- Positive signals --------------------------------------------------
    if (project_root / "diagrams").is_dir() and any(
        (project_root / "diagrams").glob("*.drawio")
    ):
        findings.append(
            GuideFinding(
                severity="ok",
                title="Architecture diagram present",
                detail="A `.drawio` diagram exists in `diagrams/`.",
                paths=["diagrams/"],
            )
        )

    return findings


def _derive_next_steps(
    findings: list[GuideFinding], manifest: dict
) -> list[dict]:
    steps: list[dict] = []
    crit = [f for f in findings if f.severity == "critical"]
    warn = [f for f in findings if f.severity == "warning"]

    needs_regen = any(
        f.title.startswith(
            (
                "Network tier is public",
                "Observability disabled",
                "infra/main.bicep is a starter",
                "Only starter service scaffold",
            )
        )
        for f in crit + warn
    )

    if needs_regen:
        steps.append(
            {
                "agent": "azure-architecture-implementer",
                "why": "Regenerate infra + services so they match the BRD and diagram.",
                "args": {
                    "project-path": f"projects/{manifest.get('project', '<slug>')}",
                    "networkTier": "private",
                    "enableObservability": True,
                },
            }
        )

    if any(
        f.title.startswith("Bicep validation") for f in crit
    ):
        steps.append(
            {
                "agent": "bicep-infrastructure-validator",
                "why": "Catch Bicep syntax/logic errors before deploy.",
                "args": {
                    "project-path": f"projects/{manifest.get('project', '<slug>')}"
                },
            }
        )

    if any(
        f.title.startswith("Production readiness") for f in crit
    ):
        steps.append(
            {
                "agent": "production-environment-advisor",
                "why": "Confirm identity, secrets, networking, and monitoring gates.",
                "args": {
                    "project-path": f"projects/{manifest.get('project', '<slug>')}"
                },
            }
        )

    if not steps:
        steps.append(
            {
                "agent": "azure-project-deployer",
                "why": "All gates pass — project looks ready to deploy.",
                "args": {
                    "project-path": f"projects/{manifest.get('project', '<slug>')}",
                    "environment": "dev",
                },
            }
        )
    return steps


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _severity_counts(findings: Iterable[GuideFinding]) -> dict:
    counts = {"critical": 0, "warning": 0, "advisory": 0, "ok": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _render_report(
    *,
    project_root: Path,
    manifest: dict,
    findings: list[GuideFinding],
    next_steps: list[dict],
    generated_at_iso: str,
) -> str:
    slug = manifest.get("project") or project_root.name
    title = manifest.get("title") or slug
    opts = manifest.get("generation_options", {}) or {}
    counts = _severity_counts(findings)

    lines: list[str] = []
    lines.append(f"# 🧭 Guide Report — {title}")
    lines.append("")
    lines.append(
        f"_Generated at **{generated_at_iso}** by the factory guide report generator "
        "(deterministic, no LLM). Regenerate any time by re-running "
        "`scripts/generate_guide_report.py` or by clicking **🧭 Guide Me → Refresh**._"
    )
    lines.append("")
    lines.append("## Snapshot")
    lines.append("")
    lines.append(f"- **Project slug:** `{slug}`")
    lines.append(f"- **Status (manifest):** `{manifest.get('status', 'unknown')}`")
    lines.append(
        f"- **Network tier:** `{opts.get('networkTier', 'unknown')}`  "
        f"**Observability:** `{opts.get('enableObservability', False)}`"
    )
    lines.append(
        f"- **Findings:** 🔴 {counts['critical']} critical · 🟠 {counts['warning']} warning · "
        f"🟡 {counts['advisory']} advisory · ✅ {counts['ok']} ok"
    )
    lines.append("")

    def section(symbol: str, label: str, severity: str) -> None:
        items = [f for f in findings if f.severity == severity]
        if not items:
            return
        lines.append(f"## {symbol} {label}")
        lines.append("")
        for f in items:
            lines.append(f"### {f.title}")
            lines.append("")
            lines.append(f.detail)
            if f.paths:
                lines.append("")
                lines.append(
                    "Related: " + ", ".join(f"`{p}`" for p in f.paths)
                )
            lines.append("")

    section("🔴", "Critical", "critical")
    section("🟠", "Warnings", "warning")
    section("🟡", "Advisory", "advisory")
    section("✅", "Looking good", "ok")

    lines.append("## ✅ What to do next")
    lines.append("")
    for i, step in enumerate(next_steps, start=1):
        args_md = ", ".join(
            f"`{k}: {v}`" for k, v in (step.get("args") or {}).items()
        )
        lines.append(
            f"{i}. **Run agent `{step['agent']}`** — {step['why']}"
        )
        if args_md:
            lines.append(f"   - Arguments: {args_md}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "> This report is a static snapshot. For a live analysis that reads "
        "current file content, open the project in VS Code Desktop or "
        "vscode.dev and run the `factory-workflow-guide` agent in Copilot Chat."
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: generate_guide_report.py <project_path> [brd_path]", file=sys.stderr)
        return 2
    project_path = Path(argv[1])
    brd_path = Path(argv[2]) if len(argv) > 2 else None
    result = generate_guide_report(project_path, brd_path)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
