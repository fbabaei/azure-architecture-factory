"""Tests for the worker's indexer-trigger gating logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from casewright.core.models import SyncRequest, SyncResult
from casewright.worker.sb_worker import MAX_DELIVERY_COUNT, SyncWorker


def _worker_with_mocks(result: SyncResult) -> tuple[SyncWorker, AsyncMock]:
    worker = object.__new__(SyncWorker)  # bypass __init__ (no Azure clients)
    worker._sync = AsyncMock()
    worker._sync.sync_site = AsyncMock(return_value=result)
    pipeline = AsyncMock()
    pipeline.run_indexer = AsyncMock()
    worker._pipeline = pipeline
    return worker, pipeline.run_indexer


@pytest.mark.asyncio
async def test_indexer_triggered_when_net_changes():
    result = SyncResult(site_id="s1", added=1)
    worker, run_indexer = _worker_with_mocks(result)

    await worker.handle(SyncRequest(tenant_id="t1", site_id="s1"))

    assert run_indexer.await_count >= 1
    assert result.indexer_triggered is True


@pytest.mark.asyncio
async def test_indexer_skipped_when_no_net_changes():
    result = SyncResult(site_id="s1", unchanged=5)
    worker, run_indexer = _worker_with_mocks(result)

    await worker.handle(SyncRequest(tenant_id="t1", site_id="s1"))

    run_indexer.assert_not_awaited()
    assert result.indexer_triggered is False


def _bare_worker() -> SyncWorker:
    return object.__new__(SyncWorker)  # bypass __init__ (no Azure clients)


def test_poison_message_is_dead_lettered():
    worker = _bare_worker()
    receiver = MagicMock()
    message = MagicMock()
    message.__str__ = lambda self: "not-json"

    worker._process_message(receiver, message)

    receiver.dead_letter_message.assert_called_once()
    receiver.complete_message.assert_not_called()
    receiver.abandon_message.assert_not_called()


def test_transient_failure_is_abandoned():
    worker = _bare_worker()
    worker.handle = AsyncMock(side_effect=RuntimeError("transient"))
    receiver = MagicMock()
    valid = SyncRequest(tenant_id="t1", site_id="s1").model_dump_json()
    message = MagicMock(delivery_count=0)
    message.__str__ = lambda self: valid

    worker._process_message(receiver, message)

    receiver.abandon_message.assert_called_once()
    receiver.dead_letter_message.assert_not_called()


def test_repeated_failure_is_dead_lettered_at_max():
    worker = _bare_worker()
    worker.handle = AsyncMock(side_effect=RuntimeError("still failing"))
    receiver = MagicMock()
    valid = SyncRequest(tenant_id="t1", site_id="s1").model_dump_json()
    message = MagicMock(delivery_count=MAX_DELIVERY_COUNT - 1)
    message.__str__ = lambda self: valid

    worker._process_message(receiver, message)

    receiver.dead_letter_message.assert_called_once()
    receiver.abandon_message.assert_not_called()


def test_successful_message_is_completed():
    worker = _bare_worker()
    worker.handle = AsyncMock(return_value=None)
    receiver = MagicMock()
    valid = SyncRequest(tenant_id="t1", site_id="s1").model_dump_json()
    message = MagicMock(delivery_count=0)
    message.__str__ = lambda self: valid

    worker._process_message(receiver, message)

    receiver.complete_message.assert_called_once()
    receiver.dead_letter_message.assert_not_called()
    receiver.abandon_message.assert_not_called()
