"""Telemetry helpers — emit structured traces to Application Insights."""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_ai_client = None


def _get_ai_client(connection_string: str):
    global _ai_client
    if _ai_client is not None:
        return _ai_client
    try:
        from opencensus.ext.azure import log_exporter  # type: ignore[import]
        from opencensus.ext.azure.trace_exporter import AzureExporter  # type: ignore[import]
        from opencensus.trace.samplers import AlwaysOnSampler  # type: ignore[import]
        from opencensus.trace.tracer import Tracer  # type: ignore[import]

        _ai_client = Tracer(
            exporter=AzureExporter(connection_string=connection_string),
            sampler=AlwaysOnSampler(),
        )
    except ImportError:
        logger.debug("opencensus not installed; telemetry will use structured logging only.")
    return _ai_client


def emit_trace(
    agent_name: str,
    task: str,
    session_id: str,
    outcome: str,
    metadata: Optional[dict[str, Any]] = None,
    settings=None,
    duration_ms: Optional[float] = None,
    token_usage: Optional[dict[str, int]] = None,
) -> None:
    """Emit a structured trace event for an agent invocation."""
    record: dict[str, Any] = {
        "event": "agent_trace",
        "agent_name": agent_name,
        "task": task,
        "session_id": session_id,
        "outcome": outcome,
    }
    if metadata:
        record["metadata"] = metadata
    if duration_ms is not None:
        record["duration_ms"] = duration_ms
    if token_usage is not None:
        record["token_usage"] = token_usage

    logger.info("TRACE %s", record)

    if settings and getattr(settings, "applicationinsights_connection_string", ""):
        client = _get_ai_client(settings.applicationinsights_connection_string)
        if client is not None:
            try:
                with client.span(name=f"{agent_name}/{task}") as span:
                    for k, v in record.items():
                        span.add_attribute(k, str(v))
            except Exception as exc:
                logger.debug("AI trace failed: %s", exc)
