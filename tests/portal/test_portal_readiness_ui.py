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


def test_portal_has_ai_factory_service_tabs_and_user_map():
    html = _portal_html()

    assert "AI Factory Services" in html
    assert "Azure Architecture Factory" in html
    assert "Agent Application Factory" in html
    assert "AI Apps &amp; Agents as a Service" in html
    assert 'id="user-map-panel"' in html
    assert "function openUserMapModal" in html
    assert "function closeUserMapModal" in html
    assert "Back to portal" in html
    assert "portal-navigation-diagram-toolbar" in html


def test_agent_factory_links_to_browser_and_workspace():
    html = _portal_html()

    assert 'href="agent-foundry/browser/index.html"' in html
    assert 'id="ai-agent-foundry-panel"' in html
    assert "Agent Browser" in html
    assert "Agent Assistant" in html


def test_user_map_renders_mermaid_when_modal_opens():
    html = _portal_html()

    assert "mermaid.min.js" in html
    assert "function renderPortalNavigationGuide()" in html
    assert "mermaid.initialize({ startOnLoad: false" in html
    assert "mermaid.run({ nodes: [diagram] })" in html
    assert "diagram.classList.add('mermaid')" in html
    assert 'class="portal-navigation-diagram"' in html
    assert 'class="portal-navigation-diagram mermaid"' not in html


def test_user_map_contains_portal_navigation_flow():
    html = _portal_html()

    assert "flowchart TD" in html
    assert 'Start["Open AI Factory Services Portal"]' in html
    assert 'AAF["Azure Architecture Factory"]' in html
    assert 'AAFac["Agent Application Factory"]' in html
    assert 'AAPAAS["AI Apps and Agents as a Service"]' in html
    assert 'Done["Validated app or agent offering"]' in html


def test_user_map_modal_hides_floating_helper_while_open():
    html = _portal_html()

    assert "body.user-map-modal-open #fab-helper-container" in html
    assert "display: none !important" in html
    assert "pointer-events: none !important" in html
