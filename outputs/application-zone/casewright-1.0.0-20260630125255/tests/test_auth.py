"""Unit tests for the optional inbound-auth / OBO dependencies."""
from __future__ import annotations

import pytest

from casewright.api import auth
from casewright.core.settings import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        GRAPH_TENANT_ID="",
        GRAPH_CLIENT_ID="",
        GRAPH_CLIENT_SECRET="",
        API_REQUIRE_JWT_VALIDATION=False,
        API_OBO_ENABLED=False,
    )
    base.update(overrides)
    return Settings(**base)


def test_extract_bearer():
    assert auth._extract_bearer("Bearer abc") == "abc"
    assert auth._extract_bearer("bearer abc") == "abc"
    assert auth._extract_bearer("Basic abc") is None
    assert auth._extract_bearer(None) is None
    assert auth._extract_bearer("Bearer ") is None


@pytest.mark.asyncio
async def test_get_optional_bearer_token():
    assert await auth.get_optional_bearer_token("Bearer t") == "t"
    assert await auth.get_optional_bearer_token(None) is None


@pytest.mark.asyncio
async def test_passthrough_when_validation_disabled():
    settings = _settings(API_REQUIRE_JWT_VALIDATION=False)
    assert await auth.get_sync_graph_access_token("raw-token", settings) == "raw-token"
    assert await auth.get_sync_graph_access_token(None, settings) is None


@pytest.mark.asyncio
async def test_no_token_returns_none_when_validation_enabled():
    settings = _settings(API_REQUIRE_JWT_VALIDATION=True)
    assert await auth.get_sync_graph_access_token(None, settings) is None


@pytest.mark.asyncio
async def test_app_only_token_returns_none(monkeypatch):
    settings = _settings(API_REQUIRE_JWT_VALIDATION=True, API_OBO_ENABLED=True)
    # App-only token: no scp claim -> no OBO, app identity used (None).
    monkeypatch.setattr(auth, "_validate_access_token", lambda token, s: {"roles": ["X"]})
    assert await auth.get_sync_graph_access_token("app-jwt", settings) is None


@pytest.mark.asyncio
async def test_delegated_token_triggers_obo_exchange(monkeypatch):
    settings = _settings(API_REQUIRE_JWT_VALIDATION=True, API_OBO_ENABLED=True)
    monkeypatch.setattr(auth, "_validate_access_token", lambda token, s: {"scp": "Files.Read"})

    async def _fake_obo(user_assertion, s):
        assert user_assertion == "user-jwt"
        return "graph-obo-token"

    monkeypatch.setattr(auth, "_exchange_graph_token_obo", _fake_obo)
    assert await auth.get_sync_graph_access_token("user-jwt", settings) == "graph-obo-token"


@pytest.mark.asyncio
async def test_delegated_token_without_obo_enabled_returns_none(monkeypatch):
    settings = _settings(API_REQUIRE_JWT_VALIDATION=True, API_OBO_ENABLED=False)
    monkeypatch.setattr(auth, "_validate_access_token", lambda token, s: {"scp": "Files.Read"})
    assert await auth.get_sync_graph_access_token("user-jwt", settings) is None


def test_is_delegated_token():
    assert auth._is_delegated_token({"scp": "Files.Read"}) is True
    assert auth._is_delegated_token({"roles": ["X"]}) is False
    assert auth._is_delegated_token({}) is False
