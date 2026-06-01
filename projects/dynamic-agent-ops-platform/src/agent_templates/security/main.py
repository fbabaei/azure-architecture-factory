"""Security Agent — CVE scanning, RBAC audit, compliance checks."""
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

AGENT_TYPE = "security"
SYSTEM_PROMPT = (
    "You are a cloud security engineer with deep expertise in Azure security. "
    "Audit Azure resources for security misconfigurations, scan for CVEs in dependencies, "
    "verify RBAC follows least-privilege principles, and ensure compliance with "
    "organizational and regulatory policies. Report findings with severity levels "
    "(critical, major, minor) and remediation guidance."
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    logger.info("DAOP Security Agent starting.")
    yield


def create_app() -> FastAPI:
    settings = AgentSettings(agent_type=AGENT_TYPE)
    app = FastAPI(title="DAOP Security Agent", version="1.0.0", lifespan=lifespan)
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
        logger.exception("Security agent run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8094"))
    uvicorn.run("agent_templates.security.main:app", host="0.0.0.0", port=port, reload=False)
