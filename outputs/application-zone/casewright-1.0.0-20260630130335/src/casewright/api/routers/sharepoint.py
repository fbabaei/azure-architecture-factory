from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from casewright.api.auth import get_sync_graph_access_token
from casewright.core.models import SyncRequest
from casewright.core.settings import get_settings
from casewright.sharepoint.graph_client import SharePointGraphClient
from casewright.sharepoint.sync_dispatcher import SyncDispatcher

router = APIRouter(prefix="/sharepoint", tags=["sharepoint"])


@lru_cache
def _get_graph() -> SharePointGraphClient:
    return SharePointGraphClient()


def _graph_for(delegated_token: str | None) -> SharePointGraphClient:
    """Per-request client bound to the user's delegated token, or the shared app-identity client."""
    if delegated_token:
        return SharePointGraphClient(delegated_token=delegated_token)
    return _get_graph()


@lru_cache
def _get_dispatcher() -> SyncDispatcher:
    return SyncDispatcher()


@router.get("/sites")
async def list_sites(
    delegated_token: str | None = Depends(get_sync_graph_access_token),
) -> list[dict]:
    return await _graph_for(delegated_token).list_sites()


@router.get("/sites/member-of")
async def sites_member_of(
    delegated_token: str | None = Depends(get_sync_graph_access_token),
) -> list[dict]:
    return await _graph_for(delegated_token).list_sites(member_of=True)


@router.get("/sites/member-of/{user_id}")
async def sites_member_of_user(
    user_id: str,
    search: str = "*",
    max_results: int = 200,
    delegated_token: str | None = Depends(get_sync_graph_access_token),
) -> list[dict]:
    s = get_settings()
    return await _graph_for(delegated_token).get_member_sites(
        user_id, search=search, max_results=max_results, tenant_id=s.sync_default_tenant_id
    )


@router.get("/sites/resolve")
async def resolve_site(
    hostname: str,
    site_path: str,
    delegated_token: str | None = Depends(get_sync_graph_access_token),
) -> dict[str, str]:
    site_id, display_name = await _graph_for(delegated_token).resolve_site_info(hostname, site_path)
    return {"site_id": site_id, "display_name": display_name}


@router.get("/sites/members")
async def site_members(
    site_id: str,
    delegated_token: str | None = Depends(get_sync_graph_access_token),
) -> list[dict]:
    return await _graph_for(delegated_token).list_site_members(site_id)



@router.post("/sites/sync-site")
async def sync_site(site_id: str, tenant_id: str | None = None) -> dict[str, str]:
    s = get_settings()
    request = SyncRequest(tenant_id=tenant_id or s.sync_default_tenant_id, site_id=site_id)
    await _get_dispatcher().enqueue(request)
    return {"status": "queued", "site_id": site_id}


@router.post("/sites/sync")
async def sync_all(tenant_id: str | None = None) -> dict[str, int]:
    s = get_settings()
    sites = await _get_graph().list_sites()
    for site in sites:
        await _get_dispatcher().enqueue(
            SyncRequest(tenant_id=tenant_id or s.sync_default_tenant_id, site_id=site["id"])
        )
    return {"queued": len(sites)}
