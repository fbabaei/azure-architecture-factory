from __future__ import annotations

import logging
from datetime import datetime, timezone

from .config import Settings
from .secrets import SecretResolver


logger = logging.getLogger("storage-self-service")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class LogEventPublisher:
    def publish(self, request_id: str, event_type: str, details: str) -> dict[str, str]:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "request_id": request_id,
            "event_type": event_type,
            "details": details,
            "timestamp": timestamp,
        }
        logger.info("event=%s request_id=%s details=%s", event_type, request_id, details)
        return payload


class AzureEventGridPublisher:
    def __init__(self, settings: Settings):
        from azure.core.credentials import AzureKeyCredential
        from azure.eventgrid import EventGridEvent, EventGridPublisherClient

        if settings.azure_event_grid_topic_endpoint is None:
            raise ValueError("AZURE_EVENT_GRID_TOPIC_ENDPOINT must be set for event publisher backend=eventgrid")

        resolver = SecretResolver(settings)
        topic_key = resolver.require_direct_or_secret(
            "AZURE_EVENT_GRID_TOPIC_KEY",
            "AZURE_EVENT_GRID_TOPIC_KEY_SECRET_NAME",
        )
        self._event_class = EventGridEvent
        self._client = EventGridPublisherClient(
            endpoint=settings.azure_event_grid_topic_endpoint,
            credential=AzureKeyCredential(topic_key),
        )

    def publish(self, request_id: str, event_type: str, details: str) -> dict[str, str]:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "request_id": request_id,
            "event_type": event_type,
            "details": details,
            "timestamp": timestamp,
        }
        event = self._event_class(
            subject=f"storage-self-service/{request_id}",
            event_type=event_type,
            data_version="1.0",
            data=payload,
        )
        self._client.send([event])
        logger.info("eventgrid_published=%s request_id=%s", event_type, request_id)
        return payload


def create_event_publisher(settings: Settings):
    if settings.event_backend == "eventgrid":
        return AzureEventGridPublisher(settings)
    return LogEventPublisher()


def emit_event(request_id: str, event_type: str, details: str) -> dict[str, str]:
    return LogEventPublisher().publish(request_id, event_type, details)
