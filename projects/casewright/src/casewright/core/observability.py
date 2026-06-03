"""Optional Azure Monitor / OpenTelemetry instrumentation.

Telemetry is entirely opt-in: it is a no-op unless
``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set *and* the
``azure-monitor-opentelemetry`` package is installed. This keeps local
development and the test suite free of any telemetry dependency or network
egress while giving the deployed Container Apps / Function App full distributed
tracing and custom metrics.

Custom metrics emitted:
    * ``casewright.sync.runs``           - sync requests processed (counter)
    * ``casewright.sync.net_changes``    - net file changes per sync (histogram)
    * ``casewright.indexer.runs``        - indexer executions triggered (counter)
    * ``casewright.messages.deadlettered`` - poison messages dead-lettered (counter)
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def configure_telemetry(service_name: str = "casewright") -> bool:
    """Wire Azure Monitor once per process. Returns True when enabled."""
    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not conn:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set; telemetry disabled")
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        logger.warning("azure-monitor-opentelemetry not installed; telemetry disabled")
        return False

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    configure_azure_monitor(connection_string=conn)
    logger.info("Azure Monitor telemetry configured for service %s", service_name)
    return True


@lru_cache(maxsize=1)
def _meter():
    try:
        from opentelemetry import metrics
    except ImportError:
        return None
    return metrics.get_meter("casewright")


@lru_cache(maxsize=1)
def _sync_runs():
    m = _meter()
    return m.create_counter("casewright.sync.runs", unit="1", description="Sync requests processed") if m else None


@lru_cache(maxsize=1)
def _net_changes():
    m = _meter()
    return (
        m.create_histogram("casewright.sync.net_changes", unit="1", description="Net file changes per sync")
        if m
        else None
    )


@lru_cache(maxsize=1)
def _indexer_runs():
    m = _meter()
    return m.create_counter("casewright.indexer.runs", unit="1", description="Indexer executions") if m else None


@lru_cache(maxsize=1)
def _dead_lettered():
    m = _meter()
    return (
        m.create_counter("casewright.messages.deadlettered", unit="1", description="Poison messages dead-lettered")
        if m
        else None
    )


def record_sync_run(net_changes: int, indexer_triggered: bool) -> None:
    counter = _sync_runs()
    if counter is not None:
        counter.add(1, {"indexer_triggered": indexer_triggered})
    hist = _net_changes()
    if hist is not None:
        hist.record(net_changes)


def record_indexer_run(indexer_name: str) -> None:
    counter = _indexer_runs()
    if counter is not None:
        counter.add(1, {"indexer": indexer_name})


def record_dead_lettered(reason: str) -> None:
    counter = _dead_lettered()
    if counter is not None:
        counter.add(1, {"reason": reason})
