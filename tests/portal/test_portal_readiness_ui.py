"""Regression checks for readiness-driven UI behavior in factory-portal.html."""
from __future__ import annotations

from pathlib import Path


def _portal_html() -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "factory-portal.html").read_text(encoding="utf-8")


def test_orchestrator_prompt_includes_runtime_auto():
    html = _portal_html()
    assert "runtime: auto" in html


def test_run_with_copilot_has_blocked_gate_message():
    html = _portal_html()
    assert "runtime:auto blocked for this project" in html
    assert "parseAutoFlowGate" in html


def test_repo_intake_includes_live_log_panel():
    html = _portal_html()
    assert 'id="repo-intake-log"' in html
    assert "Stage:" in html
    assert "/api/runs/${encodeURIComponent(runId)}/log" in html


def test_agent_factory_has_paired_top_section():
    html = _portal_html()
    root = Path(__file__).resolve().parents[2]
    feature = html.index('id="agent-factory-feature"')
    workspaces = html.index('id="design-analysis"')

    assert feature < workspaces
    assert 'class="agent-factory-feature"' in html
    assert 'href="agent-application-factory/browser/index.html"' in html
    assert 'href="#ai-agent-foundry-panel">Open planning workspace</a>' in html
    assert 'class="companion-strip"' in html
    assert 'src="assets/agent-application-factory-logo.svg"' in html
    assert (root / "assets" / "agent-application-factory-logo.svg").is_file()
    assert "topPair.className = 'factory-top-pair'" in html
    assert "topPair.appendChild(foundry)" in html
    assert "topPair.appendChild(hero)" in html


def test_document_viewer_renders_mermaid_diagrams():
    html = _portal_html()

    assert "mermaid.min.js" in html
    assert "function renderDocMermaidDiagrams()" in html
    assert "code.language-mermaid" in html
    assert "await renderDocMermaidDiagrams()" in html


def test_portal_links_to_aaf_workflow_diagram():
    html = _portal_html()
    root = Path(__file__).resolve().parents[2]

    assert 'href="diagrams/azure-architecture-factory-flow.mmd"' in html

    diagram = (root / "diagrams" / "azure-architecture-factory-flow.mmd").read_text(encoding="utf-8")
    assert "flowchart TB" in diagram
    for phase in ("Phase 0", "Phase 1.5", "Phase 2r", "Phase 2.5", "Phase 2.6", "Phase 2.7", "Phase 2.8", "Phase 3.7", "Phase 4.5", "Phase 7"):
        assert phase in diagram
    for phase in ("Phase U0", "Phase U1", "Phase U2", "Phase U3", "Phase U4", "Phase U4b", "Phase U5"):
        assert phase in diagram
    assert "Greenfield mode" in diagram
    assert "Update mode" in diagram
    assert "ACA Express" in diagram
