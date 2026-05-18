"""Unit tests for BRD content validation.

Exercises the shared ``_validate_brd_content`` helper used by both the
JSON intake endpoint and the multipart upload endpoint.
"""
from __future__ import annotations

import start_factory_portal as portal


def test_accepts_valid_markdown():
    content = "# Title\n\n" + ("Lorem ipsum " * 10)
    result, err = portal._validate_brd_content(content)
    assert err is None
    assert result is not None
    assert result.startswith("# Title")


def test_rejects_non_string():
    result, err = portal._validate_brd_content(123)
    assert result is None
    assert "string" in err.lower()


def test_rejects_empty():
    for value in ["", "   ", "\n\n\t"]:
        result, err = portal._validate_brd_content(value)
        assert result is None
        assert "empty" in err.lower()


def test_rejects_too_short(monkeypatch):
    monkeypatch.setattr(portal, "MIN_BRD_CONTENT_CHARS", 50)
    result, err = portal._validate_brd_content("short")
    assert result is None
    assert "too short" in err.lower()


def test_rejects_too_long(monkeypatch):
    monkeypatch.setattr(portal, "MAX_BRD_CONTENT_CHARS", 100)
    result, err = portal._validate_brd_content("x" * 200)
    assert result is None
    assert "too long" in err.lower()


def test_rejects_nul_byte():
    payload = "Valid BRD content\n" + "\x00 embedded null " + ("a" * 100)
    result, err = portal._validate_brd_content(payload)
    assert result is None
    assert "control" in err.lower()


def test_rejects_other_control_chars():
    # 0x07 = BEL, which is a C0 control byte and not whitespace
    payload = "Valid BRD content\n" + "\x07 embedded bell " + ("a" * 100)
    result, err = portal._validate_brd_content(payload)
    assert result is None
    assert "control" in err.lower()


def test_allows_standard_whitespace():
    # Tab, LF, CR must be permitted even though they are C0 controls
    payload = "# Title\n\n\tindented\r\nmore text " + ("a" * 100)
    result, err = portal._validate_brd_content(payload)
    assert err is None
    assert result is not None
