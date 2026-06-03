"""Thin Microsoft Graph wrapper for SharePoint site + file enumeration.

By default the client authenticates with the same managed identity used elsewhere (app-only
Graph access). When a *delegated_token* is supplied, Graph calls run on-behalf-of the signed-in
user, so results are security-trimmed to that user's permissions. Only the read operations
Casewright needs are exposed: resolve a site by hostname/path, list sites and their members,
discover a user's member sites, and enumerate drive items (files) for a site so the delta-sync
can classify changes.
"""
from __future__ import annotations

import logging
import urllib.parse

import httpx

from casewright.core.clients import get_credential

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


def _normalize_sites_search(search: str | None) -> str:
    """Append a trailing wildcard for prefix matching unless one is already present."""
    value = (search or "").strip()
    if not value or value == "*":
        return value or "*"
    if "*" in value:
        return value
    return f"{value}*"


class SharePointGraphClient:
    def __init__(self, delegated_token: str | None = None) -> None:
        # A delegated (on-behalf-of) token makes every Graph call run as the signed-in user so
        # results respect that user's SharePoint permissions. Without one we fall back to the
        # app/managed identity used everywhere else.
        self._delegated_token = (delegated_token or "").strip() or None
        self._credential = None if self._delegated_token else get_credential()

    def _token(self) -> str:
        if self._delegated_token:
            return self._delegated_token
        return self._credential.get_token(GRAPH_SCOPE).token

    def _headers(self, *, consistency: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token()}"}
        if consistency:
            # Required for Graph $search / $count over directory objects (groups, members).
            headers["ConsistencyLevel"] = "eventual"
        return headers

    async def _get(self, path: str, *, consistency: bool = False) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{GRAPH_BASE}{path}", headers=self._headers(consistency=consistency)
            )
            resp.raise_for_status()
            return resp.json()

    async def resolve_site_info(self, hostname: str, site_path: str) -> tuple[str, str]:
        """Resolve a SharePoint site to its (site_id, display_name) by hostname + server-relative path.

        Example: ``resolve_site_info("contoso.sharepoint.com", "/sites/Legal")``.
        """
        hostname = (hostname or "").strip()
        path = (site_path or "").strip()
        if not hostname or not path:
            raise ValueError("hostname and site_path are required.")
        if not path.startswith("/"):
            path = f"/{path}"
        data = await self._get(f"/sites/{hostname}:{path}")
        site_id = data.get("id")
        if not site_id:
            raise ValueError(f"Could not resolve SharePoint site at {hostname}{path}.")
        display_name = str(data.get("displayName") or data.get("name") or "").strip()
        return site_id, display_name

    async def search_sites(self, search: str = "*", max_results: int = 200) -> list[dict]:
        """Search sites via the Graph search surface, returning id/displayName/webUrl entries."""
        encoded = urllib.parse.quote(_normalize_sites_search(search))
        path: str | None = f"/sites?search={encoded}&$select=id,displayName,webUrl"
        sites: list[dict] = []
        while path and len(sites) < max_results:
            payload = await self._get(path, consistency=True)
            for site in payload.get("value", []):
                sites.append(
                    {
                        "id": str(site.get("id") or ""),
                        "displayName": str(site.get("displayName") or ""),
                        "webUrl": str(site.get("webUrl") or ""),
                    }
                )
                if len(sites) >= max_results:
                    break
            next_link = payload.get("@odata.nextLink")
            path = next_link.replace(GRAPH_BASE, "") if next_link else None
        return sites

    async def get_member_sites(
        self,
        user_id: str,
        search: str = "*",
        max_results: int = 200,
        tenant_id: str | None = None,
    ) -> list[dict]:
        """List sites whose connected group the given user belongs to (transitively)."""
        identifier = (user_id or "").strip()
        if not identifier:
            raise ValueError("user_id is required.")

        sites = await self.search_sites(search=search, max_results=max_results)
        member_sites: list[dict] = []
        for site in sites:
            site_id = str(site.get("id") or "").strip()
            if not site_id:
                continue
            group_id = await self._resolve_connected_group_id(site_id)
            if not group_id:
                continue
            if not await self._is_user_member_of_group(group_id, identifier):
                continue
            member_sites.append(
                {
                    "site_id": site_id,
                    "site_name": str(site.get("displayName") or ""),
                    "web_url": str(site.get("webUrl") or ""),
                }
            )
        member_sites.sort(key=lambda s: (s.get("site_name") or "", s.get("site_id") or ""))
        return member_sites

    async def list_sites(self, member_of: bool = False) -> list[dict]:
        # member_of narrows to sites the signed-in identity follows; both use the search surface.
        path = "/sites?search=*" if not member_of else "/me/followedSites"
        data = await self._get(path)
        return data.get("value", [])

    async def list_site_members(self, site_id: str) -> list[dict]:
        data = await self._get(f"/sites/{site_id}/permissions")
        return data.get("value", [])

    async def list_drive_items(self, site_id: str) -> list[dict]:
        """Return all files in the site's default document library with id/name/eTag/lastModified."""
        drive = await self._get(f"/sites/{site_id}/drive")
        drive_id = drive["id"]
        items: list[dict] = []
        path: str | None = f"/drives/{drive_id}/root/children"
        while path:
            data = await self._get(path)
            for entry in data.get("value", []):
                if entry.get("file"):
                    items.append(entry)
            next_link = data.get("@odata.nextLink")
            path = next_link.replace(GRAPH_BASE, "") if next_link else None
        return items

    async def download_item(self, site_id: str, item_id: str) -> bytes:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/sites/{site_id}/drive/items/{item_id}/content",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.content

    # ------------------------------------------------------------------ #
    # group-membership helpers (used by get_member_sites)                #
    # ------------------------------------------------------------------ #

    async def _resolve_connected_group_id(self, site_id: str) -> str | None:
        """Find the Microsoft 365 group connected to a site by matching display names."""
        site = await self._get(f"/sites/{site_id}?$select=displayName")
        site_display_name = str(site.get("displayName") or "").strip()
        if not site_display_name:
            return None

        search_query = urllib.parse.quote(f'"displayName:{site_display_name}"')
        groups = await self._get(
            f"/groups?$search={search_query}&$select=id,displayName", consistency=True
        )
        group_values = groups.get("value") or []
        if not group_values:
            return None
        exact = next(
            (
                g
                for g in group_values
                if str(g.get("displayName") or "").strip().lower() == site_display_name.lower()
            ),
            None,
        )
        target = exact or group_values[0]
        return str(target.get("id") or "") or None

    async def _is_user_member_of_group(self, group_id: str, user_id: str) -> bool:
        identifier = str(user_id or "").strip().lower()
        if not identifier:
            return False
        path: str | None = (
            f"/groups/{group_id}/transitiveMembers/microsoft.graph.user"
            "?$select=id,userPrincipalName,mail"
        )
        while path:
            payload = await self._get(path, consistency=True)
            for member in payload.get("value", []):
                if identifier in {
                    str(member.get("id") or "").strip().lower(),
                    str(member.get("userPrincipalName") or "").strip().lower(),
                    str(member.get("mail") or "").strip().lower(),
                }:
                    return True
            next_link = payload.get("@odata.nextLink")
            path = next_link.replace(GRAPH_BASE, "") if next_link else None
        return False
