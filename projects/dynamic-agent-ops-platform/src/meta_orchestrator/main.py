"""Meta-Orchestrator Agent Service — entry point.

Exposes a FastAPI application with:
  POST /orchestrate   — accept a natural-language goal, decompose it, spin up
                         sub-agents, and return the assembled result.
  GET  /sessions/{id} — retrieve the current state of an orchestration session.
  POST /sessions/{id}/approve — HITL approval endpoint.
  GET  /health        — liveness probe.
  GET  /health/ready  — readiness probe.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from meta_orchestrator.config import Settings
from meta_orchestrator.routers import health, orchestrate, sessions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    settings: Settings = app.state.settings  # type: ignore[attr-defined]
    logger.info(
        "DAOP Meta-Orchestrator starting — foundry_runtime_enabled=%s",
        settings.foundry_runtime_enabled,
    )
    yield
    logger.info("DAOP Meta-Orchestrator shutting down.")


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="DAOP Meta-Orchestrator",
        version="1.0.0",
        description="Dynamic Agent Orchestration Platform — meta-orchestrator entry point.",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(orchestrate.router, prefix="/orchestrate")
    app.include_router(sessions.router, prefix="/sessions")

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("meta_orchestrator.main:app", host="0.0.0.0", port=port, reload=False)
