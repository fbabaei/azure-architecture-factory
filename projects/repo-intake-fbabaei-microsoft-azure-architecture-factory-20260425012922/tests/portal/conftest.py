"""Shared fixtures for portal tests.

Puts ``scripts/`` on sys.path so test modules can import ``telemetry``
and ``start_factory_portal`` directly, matching how the portal runs
inside its container.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
