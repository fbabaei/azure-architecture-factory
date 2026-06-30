"""Enqueues SharePoint sync requests onto Service Bus.

The API and the scheduler both produce sync requests; the worker consumes them. Decoupling via a
queue means a burst of site syncs never blocks the request thread and retries are handled by the
broker.
"""
from __future__ import annotations

import asyncio
import logging

from casewright.core.clients import get_credential
from casewright.core.models import SyncRequest
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)


class SyncDispatcher:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def enqueue(self, request: SyncRequest) -> None:
        await asyncio.to_thread(self._enqueue_sync, request)

    def _enqueue_sync(self, request: SyncRequest) -> None:
        from azure.servicebus import ServiceBusClient, ServiceBusMessage

        s = self._settings
        client = ServiceBusClient(
            fully_qualified_namespace=s.servicebus_namespace, credential=get_credential()
        )
        with client:
            sender = client.get_queue_sender(queue_name=s.servicebus_queue_name)
            with sender:
                sender.send_messages(ServiceBusMessage(request.model_dump_json()))
        logger.info("enqueued sync for site %s tenant %s", request.site_id, request.tenant_id)
