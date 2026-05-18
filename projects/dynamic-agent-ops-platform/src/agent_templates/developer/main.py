"""Developer Agent — MAF-powered code generation, review, and test writing."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict

from agent_templates.shared.base_agent import BaseAgentRunner, TaskRequest, TaskResult
from agent_templates.shared.config import AgentSettings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

AGENT_TYPE = "developer"
SYSTEM_PROMPT = (
    "You are an expert software engineer specializing in Python and .NET. "
    "Generate clean, well-tested, production-ready code that follows the project conventions. "
    "Always include error handling, structured logging, and appropriate tests. "
    "Prefer explicit dependency injection over module-level globals."
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    logger.info("DAOP Developer Agent starting.")
    yield


def create_app() -> FastAPI:
    settings = AgentSettings(agent_type=AGENT_TYPE)
    app = FastAPI(title="DAOP Developer Agent", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    return app


app = create_app()


class RunRequest(BaseModel):
    session_id: str
    project_id: str
    task: Dict[str, Any]
    hitl_enabled: bool = True


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/health/ready")
async def readiness() -> JSONResponse:
    return JSONResponse({"status": "ready"})


@app.post("/run")
async def run_task(body: RunRequest, request: Request) -> TaskResult:
    settings: AgentSettings = request.app.state.settings  # type: ignore[attr-defined]
    runner = BaseAgentRunner(
        agent_type=AGENT_TYPE,
        system_prompt=SYSTEM_PROMPT,
        settings=settings,
    )
    try:
        return await runner.run(
            TaskRequest(
                session_id=body.session_id,
                project_id=body.project_id,
                task=body.task,
                hitl_enabled=body.hitl_enabled,
            )
        )
    except Exception as exc:
        logger.exception("Developer agent run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8091"))
    uvicorn.run("agent_templates.developer.main:app", host="0.0.0.0", port=port, reload=False)
