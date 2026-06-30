"""Application configuration loaded from environment variables.

A single immutable :class:`AppConfig` instance is loaded at startup and
passed to the composition root. Modules should accept the values they need,
not the whole config, to keep dependencies explicit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the Teams bot."""

    project_endpoint: str
    agent_name: str
    port: int
    broadcast_command: str

    # Bot identity (Phase 4). Required by Bot Service request validation when
    # ``skip_auth`` is False; left empty for local Agents Playground testing.
    client_id: str | None
    client_secret: str | None
    tenant_id: str | None
    skip_auth: bool

    # Cosmos DB conversation-reference store (Phase 5). When the endpoint,
    # database, and container are all set, proactive state is persisted there;
    # otherwise an in-memory fallback is used.
    cosmos_endpoint: str | None
    cosmos_database: str | None
    cosmos_container: str
    cosmos_key: str | None

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        project_endpoint = (os.getenv("PROJECT_ENDPOINT") or "").strip()
        agent_name = (os.getenv("AGENT_NAME") or "").strip()
        if not project_endpoint or not agent_name:
            raise RuntimeError(
                "PROJECT_ENDPOINT and AGENT_NAME must be set in the "
                "environment (see .env)."
            )

        # Default to skipping auth so local Agents Playground keeps working;
        # set SKIP_AUTH=false in deployed environments to validate incoming
        # Bot Service requests.
        skip_auth = _as_bool(os.getenv("SKIP_AUTH"), default=True)
        client_id = (os.getenv("CLIENT_ID") or "").strip() or None
        client_secret = (os.getenv("CLIENT_SECRET") or "").strip() or None
        tenant_id = (os.getenv("TENANT_ID") or "").strip() or None

        if not skip_auth and not (client_id and client_secret and tenant_id):
            raise RuntimeError(
                "SKIP_AUTH is false but CLIENT_ID, CLIENT_SECRET, and "
                "TENANT_ID are not all set (see .env)."
            )

        return cls(
            project_endpoint=project_endpoint,
            agent_name=agent_name,
            port=int(os.getenv("PORT", "3978")),
            broadcast_command=(
                os.getenv("BROADCAST_COMMAND", "broadcast").strip().lower()
            ),
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            skip_auth=skip_auth,
            cosmos_endpoint=(os.getenv("COSMOS_ENDPOINT") or "").strip() or None,
            cosmos_database=(os.getenv("COSMOS_DATABASE") or "").strip() or None,
            cosmos_container=(
                os.getenv("COSMOS_CONTAINER") or "conversation_references"
            ).strip(),
            cosmos_key=(os.getenv("COSMOS_KEY") or "").strip() or None,
        )
