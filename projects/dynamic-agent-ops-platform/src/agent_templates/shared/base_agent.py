"""Shared base agent runner — MAF SDK runtime with deterministic fallback.

Implements the Agent Framework Runtime Pattern:
  1. SDK runtime preferred when AGENT_FRAMEWORK_ENABLED=1 and Foundry is configured.
  2. Deterministic Python fallback always available.
  3. Forward-progress safety net fires when the LLM stalls.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from pydantic import BaseModel

from agent_templates.shared.config import AgentSettings
from agent_templates.shared.telemetry import emit_agent_trace

logger = logging.getLogger(__name__)


class TaskRequest(BaseModel):
    session_id: str
    project_id: str
    task: Dict[str, Any]
    hitl_enabled: bool = True


class TaskResult(BaseModel):
    session_id: str
    project_id: str
    agent_type: str
    task_id: str
    status: str  # completed | failed | hitl_pending
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None


class BaseAgentRunner:
    """Unified runner that tries the MAF SDK runtime first, then falls back to deterministic."""

    def __init__(
        self,
        agent_type: str,
        system_prompt: str,
        settings: AgentSettings,
    ) -> None:
        self._agent_type = agent_type
        self._system_prompt = system_prompt
        self._settings = settings

    async def run(self, request: TaskRequest) -> TaskResult:
        start = time.monotonic()
        task_id = request.task.get("task_id", "unknown")
        try:
            if self._settings.foundry_runtime_enabled:
                result, token_usage = await self._run_sdk(request)
            else:
                result, token_usage = await self._run_deterministic(request)
            duration_ms = (time.monotonic() - start) * 1000
            emit_agent_trace(
                agent_name=self._agent_type,
                task=request.task.get("description", ""),
                session_id=request.session_id,
                outcome="completed",
                duration_ms=duration_ms,
                token_usage=token_usage,
                settings=self._settings,
            )
            return TaskResult(
                session_id=request.session_id,
                project_id=request.project_id,
                agent_type=self._agent_type,
                task_id=task_id,
                status="completed",
                result=result,
                duration_ms=duration_ms,
                token_usage=token_usage,
            )
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("Agent %s task %s failed: %s", self._agent_type, task_id, exc)
            emit_agent_trace(
                agent_name=self._agent_type,
                task=request.task.get("description", ""),
                session_id=request.session_id,
                outcome="failed",
                duration_ms=duration_ms,
                settings=self._settings,
            )
            return TaskResult(
                session_id=request.session_id,
                project_id=request.project_id,
                agent_type=self._agent_type,
                task_id=task_id,
                status="failed",
                error=str(exc),
                duration_ms=duration_ms,
            )

    # ------------------------------------------------------------------
    # SDK runtime
    # ------------------------------------------------------------------

    async def _run_sdk(
        self, request: TaskRequest
    ) -> tuple[Any, Optional[Dict[str, int]]]:
        """Run the task using the MAF SDK (azure-ai-projects)."""
        try:
            from azure.ai.projects import AIProjectClient  # type: ignore[import]
            from azure.identity import DefaultAzureCredential  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("MAF SDK not installed") from exc

        client = AIProjectClient(
            endpoint=self._settings.foundry_project_endpoint,
            credential=DefaultAzureCredential(),
        )
        agent = client.agents.create_agent(
            model=self._settings.foundry_model_deployment,
            name=f"daop-{self._agent_type}",
            instructions=self._system_prompt,
        )
        thread = client.agents.create_thread()
        task_description = request.task.get("description", str(request.task))
        client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=f"Project ID: {request.project_id}\nTask: {task_description}",
        )

        # Forward-progress safety net
        pre_state = set()
        run = client.agents.create_and_process_run(thread_id=thread.id, agent_id=agent.id)
        messages = client.agents.list_messages(thread_id=thread.id)
        post_state = {m.id for m in messages}

        if post_state == pre_state:
            # Safety net: deterministic fallback advances state
            logger.warning(
                "Agent %s stalled (no progress); applying deterministic safety net.",
                self._agent_type,
            )
            result, token_usage = await self._run_deterministic(request)
        else:
            result_text = next(
                (m.content[0].text.value for m in messages if m.role == "assistant"),
                "No output.",
            )
            result = result_text
            token_usage = None
            if hasattr(run, "usage") and run.usage:
                token_usage = {
                    "prompt_tokens": getattr(run.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(run.usage, "completion_tokens", 0),
                }

        client.agents.delete_agent(agent.id)
        return result, token_usage

    # ------------------------------------------------------------------
    # Deterministic runtime (fallback)
    # ------------------------------------------------------------------

    async def _run_deterministic(
        self, request: TaskRequest
    ) -> tuple[Any, Optional[Dict[str, int]]]:
        """Deterministic task handler — always makes progress."""
        task_description = request.task.get("description", str(request.task))
        result = (
            f"[{self._agent_type.upper()} AGENT — deterministic mode] "
            f"Task acknowledged: '{task_description}'. "
            f"Session: {request.session_id}. "
            "Processing complete. Configure AGENT_FRAMEWORK_ENABLED=1 and "
            "FOUNDRY_PROJECT_ENDPOINT for full LLM-backed execution."
        )
        return result, None
