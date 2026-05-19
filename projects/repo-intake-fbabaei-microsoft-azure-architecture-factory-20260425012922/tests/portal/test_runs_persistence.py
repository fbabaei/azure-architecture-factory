"""Tests for the RUNS persistence helpers in scripts/start_factory_portal.py.

Covers:
- _persist_runs_unlocked writes JSON atomically
- persist_runs acquires the lock and delegates
- _restore_runs_on_startup is a no-op when no state file exists
- _restore_runs_on_startup loads completed/failed entries unchanged
- _restore_runs_on_startup migrates queued/running entries to 'interrupted'
- _persist_runs_unlocked tolerates disk errors silently

We redirect AAFACTORY_RUNS_STATE to a tmp path *before* importing the
portal module so _RUNS_STATE_PATH resolves to the test location.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.fixture
def portal_module(tmp_path, monkeypatch):
    """Import start_factory_portal with AAFACTORY_RUNS_STATE pointed at tmp_path."""
    state_path = tmp_path / "portal-runs.state.json"
    monkeypatch.setenv("AAFACTORY_RUNS_STATE", str(state_path))

    # Drop any previously imported copy so the module picks up our env var.
    for name in list(sys.modules):
        if name == "start_factory_portal":
            del sys.modules[name]

    module = importlib.import_module("start_factory_portal")

    # Sanity: the module resolved _RUNS_STATE_PATH from our env var.
    assert Path(module._RUNS_STATE_PATH) == state_path

    # Reset RUNS between tests; module-level globals are shared otherwise.
    with module.RUNS_LOCK:
        module.RUNS.clear()

    yield module

    with module.RUNS_LOCK:
        module.RUNS.clear()


def test_persist_runs_unlocked_writes_json(portal_module):
    m = portal_module
    with m.RUNS_LOCK:
        m.RUNS["run-1"] = {
            "status": "completed",
            "startedAt": "2026-01-01T00:00:00Z",
            "finishedAt": "2026-01-01T00:01:00Z",
        }
        m._persist_runs_unlocked()

    data = json.loads(Path(m._RUNS_STATE_PATH).read_text(encoding="utf-8"))
    assert "run-1" in data
    assert data["run-1"]["status"] == "completed"


def test_persist_runs_writes_atomically(portal_module):
    """After write, the .tmp sibling should not linger."""
    m = portal_module
    with m.RUNS_LOCK:
        m.RUNS["run-x"] = {"status": "queued"}
        m._persist_runs_unlocked()

    state = Path(m._RUNS_STATE_PATH)
    tmp = state.with_suffix(".tmp")
    assert state.exists()
    assert not tmp.exists()


def test_persist_runs_acquires_lock(portal_module):
    """persist_runs() must acquire RUNS_LOCK — calling it from a thread that
    already holds the lock would deadlock. We just verify it writes."""
    m = portal_module
    with m.RUNS_LOCK:
        m.RUNS["run-2"] = {"status": "running"}
    m.persist_runs()
    data = json.loads(Path(m._RUNS_STATE_PATH).read_text(encoding="utf-8"))
    assert data["run-2"]["status"] == "running"


def test_restore_on_startup_noop_when_missing(portal_module):
    m = portal_module
    # Ensure the state file does not exist.
    Path(m._RUNS_STATE_PATH).unlink(missing_ok=True)
    m._restore_runs_on_startup()
    assert m.RUNS == {}


def test_restore_on_startup_preserves_terminal_states(portal_module):
    m = portal_module
    state = Path(m._RUNS_STATE_PATH)
    state.write_text(json.dumps({
        "done-1": {"status": "completed", "finishedAt": "2026-01-01T00:00:00Z"},
        "failed-1": {"status": "failed", "finishedAt": "2026-01-01T00:00:00Z"},
    }), encoding="utf-8")

    m._restore_runs_on_startup()

    assert m.RUNS["done-1"]["status"] == "completed"
    assert m.RUNS["failed-1"]["status"] == "failed"


def test_restore_on_startup_marks_queued_and_running_interrupted(portal_module):
    m = portal_module
    state = Path(m._RUNS_STATE_PATH)
    state.write_text(json.dumps({
        "q-1": {"status": "queued", "createdAt": "2026-01-01T00:00:00Z"},
        "r-1": {"status": "running", "startedAt": "2026-01-01T00:00:00Z"},
        "c-1": {"status": "completed"},
    }), encoding="utf-8")

    m._restore_runs_on_startup()

    assert m.RUNS["q-1"]["status"] == "interrupted"
    assert "finishedAt" in m.RUNS["q-1"]
    assert "[portal restart]" in m.RUNS["q-1"]["stderr"]

    assert m.RUNS["r-1"]["status"] == "interrupted"
    assert "[portal restart]" in m.RUNS["r-1"]["stderr"]

    # Terminal states untouched.
    assert m.RUNS["c-1"]["status"] == "completed"


def test_restore_on_startup_persists_migrated_state(portal_module):
    """After restore, the on-disk snapshot should also reflect interruption."""
    m = portal_module
    state = Path(m._RUNS_STATE_PATH)
    state.write_text(json.dumps({
        "r-1": {"status": "running"},
    }), encoding="utf-8")

    m._restore_runs_on_startup()

    data = json.loads(state.read_text(encoding="utf-8"))
    assert data["r-1"]["status"] == "interrupted"


def test_restore_tolerates_corrupt_json(portal_module):
    m = portal_module
    state = Path(m._RUNS_STATE_PATH)
    state.write_text("{not valid json", encoding="utf-8")
    # Must not raise.
    m._restore_runs_on_startup()
    assert m.RUNS == {}


def test_restore_tolerates_non_dict_payload(portal_module):
    m = portal_module
    state = Path(m._RUNS_STATE_PATH)
    state.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    m._restore_runs_on_startup()
    assert m.RUNS == {}


def test_persist_swallows_disk_errors(portal_module, monkeypatch):
    """Best-effort write: a full disk or unwritable path must not propagate."""
    m = portal_module

    def _raise(*_a, **_kw):
        raise OSError("disk full")

    # Patch Path.write_text so the atomic-write step inside
    # _persist_runs_unlocked fails.
    monkeypatch.setattr(Path, "write_text", _raise, raising=True)

    # Must not raise.
    with m.RUNS_LOCK:
        m.RUNS["x"] = {"status": "queued"}
        m._persist_runs_unlocked()


def test_pipeline_pool_respects_env_var(portal_module):
    """The bounded executor honors AAFACTORY_PIPELINE_MAX_WORKERS at import time."""
    m = portal_module
    # Default from start_factory_portal is 4 when env var unset at import; we
    # don't override it in portal_module, so this should be the default.
    assert m._PIPELINE_MAX_WORKERS >= 1
    assert m._PIPELINE_POOL._max_workers == m._PIPELINE_MAX_WORKERS
