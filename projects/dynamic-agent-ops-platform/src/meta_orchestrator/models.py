"""Pydantic models for the meta-orchestrator API surface."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    architect = "architect"
    developer = "developer"
    ops = "ops"
    analyst = "analyst"
    security = "security"


class SessionStatus(str, Enum):
    pending = "pending"
    decomposing = "decomposing"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"


class SubTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_type: AgentType
    description: str
    priority: int = 1
    depends_on: List[str] = Field(default_factory=list)
    status: str = "pending"
    result: Optional[Any] = None


class OrchestrateRequest(BaseModel):
    goal: str = Field(..., description="Natural-language project goal or task description.")
    project_id: Optional[str] = Field(
        None, description="Existing project context ID. If omitted, a new context is created."
    )
    hitl_enabled: Optional[bool] = Field(
        None,
        description="Override the service-level HITL setting for this session.",
    )


class OrchestrateResponse(BaseModel):
    session_id: str
    project_id: str
    status: SessionStatus
    task_plan: List[SubTask]
    message: str


class SessionState(BaseModel):
    session_id: str
    project_id: str
    goal: str
    status: SessionStatus
    task_plan: List[SubTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: Optional[Dict[str, Any]] = None
    hitl_pending: bool = False
    hitl_prompt: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HITLApprovalRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None
