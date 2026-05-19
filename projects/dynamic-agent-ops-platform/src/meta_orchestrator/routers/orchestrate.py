"""Orchestrate router — accepts a goal and returns a session with task plan."""
from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from meta_orchestrator.config import Settings
from meta_orchestrator.models import (
    OrchestrateRequest,
    OrchestrateResponse,
    SessionStatus,
)
from meta_orchestrator.services.orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["orchestrate"])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


def get_service(settings: Settings = Depends(get_settings)) -> OrchestratorService:
    return OrchestratorService(settings)


@router.post("", response_model=OrchestrateResponse)
async def orchestrate(
    body: OrchestrateRequest,
    service: OrchestratorService = Depends(get_service),
) -> OrchestrateResponse:
    """Accept a natural-language goal, decompose it into a task plan,
    dispatch sub-agents, and return the assembled session state."""
    try:
        return await service.orchestrate(body)
    except Exception as exc:
        logger.exception("Orchestration failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
