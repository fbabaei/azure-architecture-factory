"""Tests for SyncResult net-change accounting."""
from __future__ import annotations

from casewright.core.models import SyncResult


def test_net_changes_sums_added_updated_deleted_excluding_unchanged():
    r = SyncResult(site_id="s1", added=2, updated=3, unchanged=10, deleted=1)
    assert r.net_changes == 6


def test_net_changes_zero_when_only_unchanged():
    r = SyncResult(site_id="s1", unchanged=5)
    assert r.net_changes == 0
    assert r.indexer_triggered is False
