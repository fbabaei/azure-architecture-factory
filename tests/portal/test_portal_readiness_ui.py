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
