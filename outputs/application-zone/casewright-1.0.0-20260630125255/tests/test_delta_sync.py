"""Unit tests for the pure SharePoint delta-sync classification."""
from __future__ import annotations

from casewright.sharepoint.delta_sync import classify


def test_classify_added_updated_unchanged_deleted():
    previous = {"a": "v1", "b": "v1", "c": "v1"}
    current = {"a": "v1", "b": "v2", "d": "v1"}  # a unchanged, b updated, c deleted, d added

    added, updated, unchanged, deleted = classify(current, previous)

    assert added == ["d"]
    assert updated == ["b"]
    assert unchanged == ["a"]
    assert deleted == ["c"]


def test_classify_empty_previous_is_all_added():
    current = {"x": "1", "y": "2"}

    added, updated, unchanged, deleted = classify(current, {})

    assert sorted(added) == ["x", "y"]
    assert updated == []
    assert unchanged == []
    assert deleted == []


def test_classify_empty_current_is_all_deleted():
    previous = {"x": "1", "y": "2"}

    added, updated, unchanged, deleted = classify({}, previous)

    assert added == []
    assert sorted(deleted) == ["x", "y"]


def test_classify_no_changes():
    state = {"a": "1", "b": "2"}

    added, updated, unchanged, deleted = classify(state, dict(state))

    assert added == []
    assert updated == []
    assert sorted(unchanged) == ["a", "b"]
    assert deleted == []
