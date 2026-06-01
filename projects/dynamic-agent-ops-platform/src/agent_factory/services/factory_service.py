"""Agent Factory core service — instantiates/connects agents and publishes tasks."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from agent_factory.config import Settings

logger = logging.getLogger(__name__)

# Sub-agent Container App base URLs (resolved at runtime via env or registry)
_AGENT_URLS: Dict[str, str] = {
    "architect": "http://daop-agent-architect",
    "developer": "http://daop-agent-developer",
    "ops": "http://daop-agent-ops",
    "analyst": "http://daop-agent-analyst",
    "security": "http://daop-agent-security",
}


class AgentFactoryService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def dispatch(
        self,
        session_id: str,
        project_id: str,
        task_plan: List[Dict[str, Any]],
        hitl_enabled: bool = True,
    ) -> Dict[str, Any]:
        """Publish each task to Service Bus (or direct HTTP if SB not configured)."""
        dispatched: List[str] = []
        for task in task_plan:
            agent_type = task.get("agent_type", "analyst")
            task_id = task.get("task_id", "")
            message = {
                "session_id": session_id,
                "project_id": project_id,
                "task": task,
                "hitl_enabled": hitl_enabled,
            }
            if self._settings.servicebus_namespace:
                await self._publish_to_servicebus(message)
            else:
                await self._invoke_agent_direct(agent_type, message)
            dispatched.append(task_id)
            logger.info(
                "Dispatched task %s to agent_type=%s session=%s",
                task_id,
                agent_type,
                session_id,
            )
        return {"dispatched": dispatched, "session_id": session_id}

    async def _publish_to_servicebus(self, message: Dict[str, Any]) -> None:
        """Publish a task message to the Azure Service Bus tasks queue."""
        try:
            from azure.servicebus.aio import ServiceBusClient  # type: ignore[import]
            from azure.servicebus import ServiceBusMessage  # type: ignore[import]
            from azure.identity.aio import DefaultAzureCredential  # type: ignore[import]

            fqns = f"{self._settings.servicebus_namespace}.servicebus.windows.net"
            async with ServiceBusClient(
                fully_qualified_namespace=fqns,
                credential=DefaultAzureCredential(),
            ) as client:
                sender = client.get_queue_sender(self._settings.servicebus_tasks_queue)
                async with sender:
                    await sender.send_messages(
                        ServiceBusMessage(json.dumps(message))
                    )
        except Exception as exc:
            logger.error("Service Bus publish failed: %s", exc)
            raise

    async def _invoke_agent_direct(
        self, agent_type: str, message: Dict[str, Any]
    ) -> None:
        """Fallback: directly invoke the agent's HTTP endpoint."""
        import os
        env_key = f"AGENT_{agent_type.upper()}_URL"
        base_url = os.getenv(env_key, _AGENT_URLS.get(agent_type, ""))
        if not base_url:
            logger.warning("No URL configured for agent_type=%s; task dropped.", agent_type)
            return
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{base_url}/run", json=message)
            resp.raise_for_status()

    async def resolve_template(
        self, agent_type: str, project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Query the agent registry for the best-fit template for this agent type."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._settings.agent_registry_url}/templates",
                    params={"agent_type": agent_type, "project_id": project_id},
                )
                resp.raise_for_status()
                templates = resp.json()
                return templates[0] if templates else None
        except Exception as exc:
            logger.warning("Registry lookup failed: %s", exc)
            return None
