"""Sessions router — retrieve session state and submit HITL approvals."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from meta_orchestrator.config import Settings
from meta_orchestrator.models import HITLApprovalRequest, SessionState
from meta_orchestrator.services.orchestrator_service import OrchestratorService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sessions"])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


def get_service(settings: Settings = Depends(get_settings)) -> OrchestratorService:
    return OrchestratorService(settings)


@router.get("/{session_id}", response_model=SessionState)
async def get_session(
    session_id: str,
    service: OrchestratorService = Depends(get_service),
) -> SessionState:
    state = await service.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


@router.post("/{session_id}/approve")
async def approve_session(
    session_id: str,
    body: HITLApprovalRequest,
    service: OrchestratorService = Depends(get_service),
) -> SessionState:
    state = await service.approve(session_id, body)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state
