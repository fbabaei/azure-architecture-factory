"""Pydantic models for the agent registry."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentTemplate(BaseModel):
    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    agent_type: str  # architect | developer | ops | analyst | security
    description: str
    capabilities: List[str]
    required_tools: List[str] = Field(default_factory=list)
    model_preference: str = "gpt-4o"
    system_prompt_template: str = ""
    deployment_endpoint: Optional[str] = None  # set when agent is pre-deployed
    cost_tier: str = "standard"  # standard | economy | premium
    version: str = "1.0"
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentSession(BaseModel):
    session_id: str
    project_id: str
    agent_type: str
    template_id: str
    status: str = "active"  # active | idle | suspended | completed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int = 3600
