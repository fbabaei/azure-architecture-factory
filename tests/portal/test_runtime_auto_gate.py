"""Tests for runtime:auto BRD readiness gate enforcement."""
from __future__ import annotations

import importlib
import sys


def _fresh_portal_module():
    if "start_factory_portal" in sys.modules:
        del sys.modules["start_factory_portal"]
    return importlib.import_module("start_factory_portal")


def test_runtime_auto_gate_not_applied_when_runtime_not_auto():
    portal = _fresh_portal_module()
    reason = portal._runtime_auto_gate_violation(
        {"runtime": "local"},
        {"orchestratorAutoFlow": {"eligible": False, "reason": "needs review"}},
    )
    assert reason is None


def test_runtime_auto_gate_blocks_when_ineligible():
    portal = _fresh_portal_module()
    reason = portal._runtime_auto_gate_violation(
        {"runtime": "auto"},
        {
            "orchestratorAutoFlow": {
                "eligible": False,
                "reason": "Architect review required",
            }
        },
    )
    assert reason is not None
    assert "runtime:auto blocked" in reason
    assert "Architect review required" in reason


def test_runtime_auto_gate_allows_when_eligible():
    portal = _fresh_portal_module()
    reason = portal._runtime_auto_gate_violation(
        {"orchestratorRuntime": "auto"},
        {"orchestratorAutoFlow": {"eligible": True}},
    )
    assert reason is None


def test_runtime_auto_gate_reads_nested_project_payload():
    portal = _fresh_portal_module()
    reason = portal._runtime_auto_gate_violation(
        {"runtime": "auto"},
        {
            "project": {
                "orchestratorAutoFlow": {
                    "eligible": False,
                    "reason": "Gate from project payload",
                }
            }
        },
    )
    assert reason is not None
    assert "Gate from project payload" in reason
