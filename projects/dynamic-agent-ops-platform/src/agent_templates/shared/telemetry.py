"""Shared telemetry helpers for agent templates."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def emit_agent_trace(
    agent_name: str,
    task: str,
    session_id: str,
    outcome: str,
    settings=None,
    duration_ms: Optional[float] = None,
    token_usage: Optional[Dict[str, int]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    record: Dict[str, Any] = {
        "event": "agent_trace",
        "agent_name": agent_name,
        "task": task,
        "session_id": session_id,
        "outcome": outcome,
    }
    if duration_ms is not None:
        record["duration_ms"] = round(duration_ms, 2)
    if token_usage:
        record["token_usage"] = token_usage
    if metadata:
        record["metadata"] = metadata

    logger.info("TRACE %s", record)
