"""Proactive Microsoft Teams messaging service.

Teams does not allow sending a proactive message to a user by email or UPN
— a stored ``conversation_id`` per user is required. This service:

- captures user conversation references (keyed by AAD object id) whenever
  the application calls :meth:`register_user`,
- exposes :meth:`send_to_user`, which returns a structured
  :class:`SendResult` so callers can distinguish *user not reachable* from
  *send failed*.

Reaching users who have never spoken to the bot requires installing it for
them via the Microsoft Graph teamsAppInstallation API; that is outside the
scope of this service.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Protocol

from microsoft_teams.api import MessageActivityInput
from microsoft_teams.apps import App

from conversationStore import IConversationStore

logger = logging.getLogger(__name__)


class SendResult(Enum):
    SENT = "sent"
    USER_UNKNOWN = "user_unknown"
    SEND_FAILED = "send_failed"


class ITeamsMessenger(Protocol):
    async def register_user(
        self,
        aad_object_id: str | None,
        conversation_id: str,
        *,
        tenant_id: str | None = None,
        service_url: str | None = None,
        channel_id: str | None = None,
        bot_id: str | None = None,
    ) -> None: ...

    async def send_to_user(
        self, aad_object_id: str, text: str
    ) -> SendResult: ...


class TeamsMessenger:
    """Conversation-reference registry + proactive send wrapper.

    State is delegated to an :class:`IConversationStore` so proactive sends
    survive restart/scale-out when a durable (Cosmos) store is configured.
    """

    def __init__(self, app: App, store: IConversationStore) -> None:
        self._app = app
        self._store = store

    async def register_user(
        self,
        aad_object_id: str | None,
        conversation_id: str,
        *,
        tenant_id: str | None = None,
        service_url: str | None = None,
        channel_id: str | None = None,
        bot_id: str | None = None,
    ) -> None:
        if not aad_object_id:
            return
        # Upsert on every inbound message: serviceUrl can rotate and stale
        # values silently break proactive sends.
        await self._store.upsert(
            user_key=aad_object_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            service_url=service_url,
            channel_id=channel_id,
            bot_id=bot_id,
            installed=True,
        )
        logger.debug("Registered conversation for user %s", aad_object_id)

    async def send_to_user(
        self, aad_object_id: str, text: str
    ) -> SendResult:
        record = await self._store.get(aad_object_id)
        if not record or not record.conversation_id or not record.installed:
            return SendResult.USER_UNKNOWN
        try:
            await self._app.send(
                record.conversation_id, MessageActivityInput(text=text)
            )
            return SendResult.SENT
        except Exception:
            logger.exception(
                "Failed to send proactive message to %s", aad_object_id
            )
            return SendResult.SEND_FAILED
