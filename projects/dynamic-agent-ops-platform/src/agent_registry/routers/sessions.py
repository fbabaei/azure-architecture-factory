"""Sessions router."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from agent_registry.config import Settings
from agent_registry.models import AgentSession
from agent_registry.services.registry_service import RegistryService

router = APIRouter(tags=["sessions"])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


def get_service(settings: Settings = Depends(get_settings)) -> RegistryService:
    return RegistryService(settings)


@router.get("/{session_id}", response_model=AgentSession)
async def get_session(
    session_id: str,
    service: RegistryService = Depends(get_service),
) -> AgentSession:
    s = await service.get_session(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.put("/{session_id}", response_model=AgentSession)
async def upsert_session(
    session_id: str,
    body: AgentSession,
    service: RegistryService = Depends(get_service),
) -> AgentSession:
    body.session_id = session_id
    await service.upsert_session(body)
    return body
