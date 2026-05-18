"""Templates router."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from agent_registry.config import Settings
from agent_registry.models import AgentTemplate
from agent_registry.services.registry_service import RegistryService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["templates"])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[attr-defined]


def get_service(settings: Settings = Depends(get_settings)) -> RegistryService:
    return RegistryService(settings)


@router.get("", response_model=List[AgentTemplate])
async def list_templates(
    agent_type: Optional[str] = Query(None),
    service: RegistryService = Depends(get_service),
) -> List[AgentTemplate]:
    return await service.list_templates(agent_type=agent_type)


@router.get("/{template_id}", response_model=AgentTemplate)
async def get_template(
    template_id: str,
    service: RegistryService = Depends(get_service),
) -> AgentTemplate:
    t = await service.get_template(template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@router.post("", response_model=AgentTemplate, status_code=201)
async def create_template(
    body: AgentTemplate,
    service: RegistryService = Depends(get_service),
) -> AgentTemplate:
    await service.save_template(body)
    return body
