"""Unit tests for the SharePoint Graph client: token selection + site helpers."""
from __future__ import annotations

import pytest

from casewright.sharepoint import graph_client as gc
from casewright.sharepoint.graph_client import SharePointGraphClient, _normalize_sites_search


def test_normalize_sites_search_appends_wildcard():
    assert _normalize_sites_search("Legal") == "Legal*"
    assert _normalize_sites_search("Legal*") == "Legal*"
    assert _normalize_sites_search("*") == "*"
    assert _normalize_sites_search("") == "*"
    assert _normalize_sites_search(None) == "*"


def test_delegated_token_is_used_without_credential(monkeypatch):
    # If a delegated token is supplied, get_credential must never be called.
    def _boom():  # pragma: no cover - should not run
        raise AssertionError("get_credential should not be called for delegated tokens")

    monkeypatch.setattr(gc, "get_credential", _boom)
    client = SharePointGraphClient(delegated_token="user-jwt")
    assert client._token() == "user-jwt"
    assert client._headers()["Authorization"] == "Bearer user-jwt"
    assert "ConsistencyLevel" not in client._headers()
    assert client._headers(consistency=True)["ConsistencyLevel"] == "eventual"


def test_app_identity_token_uses_credential(monkeypatch):
    class _FakeToken:
        token = "app-token"

    class _FakeCredential:
        def get_token(self, scope):
            assert scope == gc.GRAPH_SCOPE
            return _FakeToken()

    monkeypatch.setattr(gc, "get_credential", lambda: _FakeCredential())
    client = SharePointGraphClient()
    assert client._token() == "app-token"


@pytest.mark.asyncio
async def test_resolve_site_info_parses_id_and_display_name(monkeypatch):
    captured: dict[str, object] = {}

    async def _fake_get(self, path, *, consistency=False):
        captured["path"] = path
        return {"id": "site-123", "displayName": "Legal"}

    monkeypatch.setattr(SharePointGraphClient, "_get", _fake_get)
    client = SharePointGraphClient(delegated_token="x")
    site_id, name = await client.resolve_site_info("contoso.sharepoint.com", "sites/Legal")

    assert site_id == "site-123"
    assert name == "Legal"
    assert captured["path"] == "/sites/contoso.sharepoint.com:/sites/Legal"


@pytest.mark.asyncio
async def test_resolve_site_info_requires_args(monkeypatch):
    client = SharePointGraphClient(delegated_token="x")
    with pytest.raises(ValueError):
        await client.resolve_site_info("", "/sites/Legal")


@pytest.mark.asyncio
async def test_get_member_sites_filters_by_group_membership(monkeypatch):
    client = SharePointGraphClient(delegated_token="x")

    async def _fake_search(self, search="*", max_results=200):
        return [
            {"id": "s1", "displayName": "Alpha", "webUrl": "https://x/s1"},
            {"id": "s2", "displayName": "Beta", "webUrl": "https://x/s2"},
        ]

    async def _fake_group(self, site_id):
        return f"group-{site_id}"

    async def _fake_member(self, group_id, user_id):
        # User is a member of s1's group only.
        return group_id == "group-s1"

    monkeypatch.setattr(SharePointGraphClient, "search_sites", _fake_search)
    monkeypatch.setattr(SharePointGraphClient, "_resolve_connected_group_id", _fake_group)
    monkeypatch.setattr(SharePointGraphClient, "_is_user_member_of_group", _fake_member)

    result = await client.get_member_sites("user@contoso.com")

    assert [s["site_id"] for s in result] == ["s1"]
    assert result[0]["site_name"] == "Alpha"


@pytest.mark.asyncio
async def test_get_member_sites_requires_user_id():
    client = SharePointGraphClient(delegated_token="x")
    with pytest.raises(ValueError):
        await client.get_member_sites("")
