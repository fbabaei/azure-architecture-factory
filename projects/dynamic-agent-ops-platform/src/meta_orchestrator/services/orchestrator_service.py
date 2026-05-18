"""Core orchestrator service — intent decomposition, agent dispatch, HITL."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

import httpx

from meta_orchestrator.config import Settings
from meta_orchestrator.models import (
    AgentType,
    HITLApprovalRequest,
    OrchestrateRequest,
    OrchestrateResponse,
    SessionState,
    SessionStatus,
    SubTask,
)
from meta_orchestrator.services.session_store import SessionStore
from meta_orchestrator.services.telemetry import emit_trace

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deterministic task-plan builder (safety net / fallback)
# ---------------------------------------------------------------------------

_KEYWORD_TO_AGENT: list[tuple[list[str], AgentType]] = [
    (["architect", "design", "diagram", "iac", "infrastructure", "bicep"], AgentType.architect),
    (["code", "develop", "implement", "service", "api", "function"], AgentType.developer),
    (["deploy", "monitor", "incident", "ops", "pipeline", "cicd"], AgentType.ops),
    (["analyze", "cost", "estimate", "requirement", "trace"], AgentType.analyst),
    (["security", "cve", "rbac", "compliance", "audit"], AgentType.security),
]


def _deterministic_decompose(goal: str) -> list[SubTask]:
    """Heuristic decomposition when the Foundry runtime is unavailable."""
    goal_lower = goal.lower()
    seen: set[AgentType] = set()
    tasks: list[SubTask] = []
    # Always start with analyst to gather requirements
    tasks.append(
        SubTask(agent_type=AgentType.analyst, description=f"Analyze requirements for: {goal}", priority=1)
    )
    seen.add(AgentType.analyst)
    for keywords, agent_type in _KEYWORD_TO_AGENT:
        if agent_type in seen:
            continue
        if any(kw in goal_lower for kw in keywords):
            tasks.append(
                SubTask(
                    agent_type=agent_type,
                    description=f"Handle {agent_type.value} tasks for: {goal}",
                    priority=len(tasks) + 1,
                    depends_on=[tasks[0].task_id],
                )
            )
            seen.add(agent_type)
    # Always close with security review
    if AgentType.security not in seen:
        tasks.append(
            SubTask(
                agent_type=AgentType.security,
                description=f"Security review for: {goal}",
                priority=len(tasks) + 1,
                depends_on=[t.task_id for t in tasks],
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Orchestrator service
# ---------------------------------------------------------------------------


class OrchestratorService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._store = SessionStore(settings)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def orchestrate(self, request: OrchestrateRequest) -> OrchestrateResponse:
        session_id = str(uuid4())
        project_id = request.project_id or str(uuid4())
        hitl = request.hitl_enabled if request.hitl_enabled is not None else self._settings.hitl_enabled

        task_plan = await self._decompose(request.goal)

        state = SessionState(
            session_id=session_id,
            project_id=project_id,
            goal=request.goal,
            status=SessionStatus.decomposing,
            task_plan=task_plan,
            metadata={"hitl_enabled": hitl},
        )
        await self._store.save(state)
        emit_trace(
            agent_name="meta-orchestrator",
            task="decompose",
            session_id=session_id,
            outcome="task_plan_created",
            metadata={"task_count": len(task_plan)},
            settings=self._settings,
        )

        # Async dispatch — fire and don't wait inline
        asyncio.create_task(self._dispatch(state, hitl))

        return OrchestrateResponse(
            session_id=session_id,
            project_id=project_id,
            status=SessionStatus.running,
            task_plan=task_plan,
            message=f"Orchestration started. {len(task_plan)} tasks dispatched.",
        )

    async def get_session(self, session_id: str) -> Optional[SessionState]:
        return await self._store.get(session_id)

    async def approve(self, session_id: str, approval: HITLApprovalRequest) -> Optional[SessionState]:
        state = await self._store.get(session_id)
        if state is None:
            return None
        state.hitl_pending = False
        if approval.approved:
            state.status = SessionStatus.running
            asyncio.create_task(self._resume(state))
        else:
            state.status = SessionStatus.failed
            state.metadata["hitl_rejection_notes"] = approval.notes
        await self._store.save(state)
        return state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _decompose(self, goal: str) -> list[SubTask]:
        """Decompose goal using Foundry runtime when available, else deterministic."""
        if self._settings.foundry_runtime_enabled:
            try:
                return await self._foundry_decompose(goal)
            except Exception as exc:
                logger.warning("Foundry decomposition failed (%s); using deterministic fallback.", exc)
        return _deterministic_decompose(goal)

    async def _foundry_decompose(self, goal: str) -> list[SubTask]:
        """Use MAF SDK to decompose the goal into a structured task plan."""
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
            name="daop-decomposer",
            instructions=(
                "You are the DAOP task decomposer. Given a user goal, return a JSON array of sub-tasks. "
                "Each sub-task must have: agent_type (one of: architect, developer, ops, analyst, security), "
                "description (string), priority (int 1=first). Return ONLY valid JSON."
            ),
        )
        thread = client.agents.create_thread()
        client.agents.create_message(thread_id=thread.id, role="user", content=goal)
        run = client.agents.create_and_process_run(thread_id=thread.id, agent_id=agent.id)
        messages = client.agents.list_messages(thread_id=thread.id)
        raw = next(
            (m.content[0].text.value for m in messages if m.role == "assistant"),
            "[]",
        )
        client.agents.delete_agent(agent.id)
        items = json.loads(raw)
        return [SubTask(**item) for item in items]

    async def _dispatch(self, state: SessionState, hitl: bool) -> None:
        """Dispatch tasks to the Agent Factory via Service Bus."""
        state.status = SessionStatus.running
        await self._store.save(state)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._settings.agent_factory_url}/dispatch",
                    json={
                        "session_id": state.session_id,
                        "project_id": state.project_id,
                        "task_plan": [t.model_dump() for t in state.task_plan],
                        "hitl_enabled": hitl,
                    },
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.error("Dispatch to agent factory failed: %s", exc)
            state.status = SessionStatus.failed
            state.metadata["dispatch_error"] = str(exc)
            await self._store.save(state)

    async def _resume(self, state: SessionState) -> None:
        """Resume execution after HITL approval."""
        await self._dispatch(state, hitl=False)
