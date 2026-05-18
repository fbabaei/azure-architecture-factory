"""Dispatch router — receives a task plan and publishes to Service Bus."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Dict, List

from agent_factory.config import Settings
from agent_factory.services.factory_service import AgentFactoryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dispatch", tags=["dispatch"])


class DispatchRequest(BaseModel):
    session_id: str
    project_id: str
    task_plan: List[Dict[str, Any]]
    hitl_enabled: bool = True


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


def get_service(settings: Settings = Depends(get_settings)) -> AgentFactoryService:
    return AgentFactoryService(settings)


@router.post("")
async def dispatch(
    body: DispatchRequest,
    service: AgentFactoryService = Depends(get_service),
) -> Dict[str, Any]:
    try:
        result = await service.dispatch(
            session_id=body.session_id,
            project_id=body.project_id,
            task_plan=body.task_plan,
            hitl_enabled=body.hitl_enabled,
        )
        return result
    except Exception as exc:
        logger.exception("Dispatch failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
