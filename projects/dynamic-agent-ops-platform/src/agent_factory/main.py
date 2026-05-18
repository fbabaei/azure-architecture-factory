"""Agent Factory Service — entry point.

Exposes:
  POST /dispatch  — receive a task plan, instantiate/connect sub-agents via MAF SDK,
                    publish tasks to Service Bus.
  GET  /health    — liveness.
  GET  /health/ready — readiness.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_factory.config import Settings
from agent_factory.routers import dispatch, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    settings: Settings = app.state.settings  # type: ignore[attr-defined]
    logger.info(
        "DAOP Agent Factory starting — foundry_runtime_enabled=%s",
        settings.foundry_runtime_enabled,
    )
    yield
    logger.info("DAOP Agent Factory shutting down.")


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="DAOP Agent Factory",
        version="1.0.0",
        description="Instantiates and connects sub-agents at runtime via MAF SDK.",
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
    app.include_router(dispatch.router)
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run("agent_factory.main:app", host="0.0.0.0", port=port, reload=False)
