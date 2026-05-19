from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RequestStatus(str, Enum):
    pending = "PENDING"
    validating = "VALIDATING"
    provisioning = "PROVISIONING"
    governed = "GOVERNED"
    completed = "COMPLETED"
    failed = "FAILED"


class ProvisioningRequestCreate(BaseModel):
    project: str = Field(min_length=3, max_length=40)
    team: str = Field(min_length=2, max_length=40)
    environment: str = Field(pattern="^(dev|test|prod)$")
    data_class: str = Field(min_length=3, max_length=20)


class ProvisioningRequest(BaseModel):
    request_id: str
    project: str
    team: str
    environment: str
    data_class: str
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    tags: dict[str, str]
    resources: dict[str, Any] = Field(default_factory=dict)
    status_history: list[dict[str, Any]] = Field(default_factory=list)

    @staticmethod
    def new(payload: ProvisioningRequestCreate) -> "ProvisioningRequest":
        now = datetime.now(timezone.utc)
        request_id = f"req-{uuid4().hex[:12]}"
        tags = {
            "project": payload.project,
            "team": payload.team,
            "environment": payload.environment,
            "data_class": payload.data_class,
        }
        history = [{"status": RequestStatus.pending.value, "at": now.isoformat(), "message": "Request submitted"}]
        return ProvisioningRequest(
            request_id=request_id,
            project=payload.project,
            team=payload.team,
            environment=payload.environment,
            data_class=payload.data_class,
            status=RequestStatus.pending,
            created_at=now,
            updated_at=now,
            tags=tags,
            status_history=history,
        )
