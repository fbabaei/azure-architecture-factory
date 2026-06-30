"""Azure Functions scheduler — fans out SharePoint sync requests onto Service Bus.

Two triggers share one handler:
  - ScheduleSharePointSync: timer on SHAREPOINT_SYNC_SCHEDULE (default every 6h).
  - schedule_sharepoint_sync_http: POST /api/schedule/sharepoint-sync for on-demand fan-out.

The handler enumerates the tenant's sites via Graph and enqueues one SyncRequest per site so the
Service Bus worker can process each independently. No keys: managed identity throughout.
"""
from __future__ import annotations

import asyncio
import logging

import azure.functions as func

from casewright.core.models import SyncRequest
from casewright.core.settings import get_settings
from casewright.sharepoint.graph_client import SharePointGraphClient
from casewright.sharepoint.sync_dispatcher import SyncDispatcher

logger = logging.getLogger(__name__)

app = func.FunctionApp()


async def _fan_out() -> int:
    settings = get_settings()
    graph = SharePointGraphClient()
    dispatcher = SyncDispatcher()
    tenant_id = settings.sync_default_tenant_id or settings.graph_tenant_id

    sites = await graph.list_sites(member_of=True)
    count = 0
    for site in sites:
        await dispatcher.enqueue(SyncRequest(tenant_id=tenant_id, site_id=site["id"]))
        count += 1
    logger.info("scheduler enqueued %d site syncs for tenant %s", count, tenant_id)
    return count


@app.function_name(name="ScheduleSharePointSync")
@app.timer_trigger(
    schedule="%SHAREPOINT_SYNC_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def schedule_sharepoint_sync(timer: func.TimerRequest) -> None:
    enqueued = asyncio.run(_fan_out())
    logger.info("timer fan-out complete: %d sites", enqueued)


@app.function_name(name="ScheduleSharePointSyncHttp")
@app.route(route="schedule/sharepoint-sync", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def schedule_sharepoint_sync_http(req: func.HttpRequest) -> func.HttpResponse:
    enqueued = asyncio.run(_fan_out())
    return func.HttpResponse(
        body=f'{{"enqueued": {enqueued}}}', mimetype="application/json", status_code=202
    )
