"""Service Bus worker — consumes sync requests and runs the delta-sync.

The worker triggers the search indexer ONLY when the sync produced net changes
(added + updated + deleted > 0), avoiding pointless indexer runs (and cost) when SharePoint had
no relevant activity since the last sync.

Reliability model:
    * Poison messages (un-parseable payloads) are dead-lettered immediately — retrying
      can never make them valid.
    * Transient failures are abandoned so Service Bus redelivers them. After
      ``maxDeliveryCount`` attempts (configured on the queue) Service Bus moves the
      message to the dead-letter sub-queue automatically. As a belt-and-braces guard the
      worker also dead-letters explicitly once the delivery count reaches the threshold.
"""
from __future__ import annotations

import asyncio
import logging

from casewright.core.clients import get_credential
from casewright.core.models import SyncRequest
from casewright.core.observability import (
    configure_telemetry,
    record_dead_lettered,
    record_indexer_run,
    record_sync_run,
)
from casewright.core.settings import get_settings
from casewright.ingestion.pipeline import INDEXERS, IngestionPipeline
from casewright.sharepoint.delta_sync import SharePointDeltaSync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Delivery attempts before the worker proactively dead-letters a failing message.
# Should match the queue's maxDeliveryCount (infra/modules/servicebus.bicep).
MAX_DELIVERY_COUNT = 5


class SyncWorker:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._sync = SharePointDeltaSync()
        self._pipeline = IngestionPipeline()

    async def handle(self, request: SyncRequest) -> None:
        result = await self._sync.sync_site(request)
        if result.net_changes > 0:
            for indexer_name in INDEXERS:
                await self._pipeline.run_indexer(indexer_name)
                record_indexer_run(indexer_name)
            result.indexer_triggered = True
            logger.info("site %s had %d net changes; indexers triggered", request.site_id, result.net_changes)
        else:
            logger.info("site %s had no net changes; skipping indexer", request.site_id)
        record_sync_run(result.net_changes, result.indexer_triggered)

    def run(self) -> None:  # pragma: no cover - long-running loop
        from azure.servicebus import ServiceBusClient

        configure_telemetry("casewright-worker")
        s = self._settings
        client = ServiceBusClient(
            fully_qualified_namespace=s.servicebus_namespace, credential=get_credential()
        )
        with client:
            receiver = client.get_queue_receiver(queue_name=s.servicebus_queue_name)
            with receiver:
                for message in receiver:
                    self._process_message(receiver, message)

    def _process_message(self, receiver, message) -> None:  # pragma: no cover - SB integration
        from pydantic import ValidationError

        try:
            request = SyncRequest.model_validate_json(str(message))
        except (ValidationError, ValueError):
            logger.exception("un-parseable message; dead-lettering as poison")
            record_dead_lettered("invalid_payload")
            receiver.dead_letter_message(
                message,
                reason="InvalidPayload",
                error_description="Message body is not a valid SyncRequest",
            )
            return

        try:
            asyncio.run(self.handle(request))
            receiver.complete_message(message)
        except Exception:
            delivery_count = getattr(message, "delivery_count", 0) or 0
            if delivery_count >= MAX_DELIVERY_COUNT - 1:
                logger.exception("processing failed after %d attempts; dead-lettering", delivery_count + 1)
                record_dead_lettered("max_delivery_exceeded")
                receiver.dead_letter_message(
                    message,
                    reason="MaxDeliveryExceeded",
                    error_description="Exhausted retry attempts",
                )
            else:
                logger.exception("processing failed; abandoning for retry")
                receiver.abandon_message(message)


def main() -> None:  # pragma: no cover
    SyncWorker().run()


if __name__ == "__main__":  # pragma: no cover
    main()
