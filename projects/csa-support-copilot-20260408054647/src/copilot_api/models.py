from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    context: str = Field(default="", max_length=8000)
    session_id: str = Field(default="", max_length=128)
    user_id: str = Field(default="anonymous", max_length=128)


class AskResponse(BaseModel):
    answer: str
    source: str
    request_id: str
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tools_used: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class ToolSummary(BaseModel):
    name: str
    description: str


class ToolCatalogResponse(BaseModel):
    tools: list[ToolSummary]
