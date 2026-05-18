"""Agent Registry Service — Cosmos DB-backed catalog of agent templates and sessions.

Exposes:
  GET    /templates               — list all templates (optionally filter by agent_type)
  GET    /templates/{template_id} — get a single template
  POST   /templates               — register a new template
  GET    /sessions                — list active sessions
  PUT    /sessions/{session_id}   — upsert session state
  GET    /health                  — liveness
  GET    /health/ready            — readiness
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_registry.config import Settings
from agent_registry.routers import health, sessions, templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    logger.info("DAOP Agent Registry starting.")
    yield
    logger.info("DAOP Agent Registry shutting down.")


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title="DAOP Agent Registry",
        version="1.0.0",
        description="Cosmos DB-backed catalog of agent templates, capabilities, and sessions.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(templates.router, prefix="/templates")
    app.include_router(sessions.router, prefix="/sessions")
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run("agent_registry.main:app", host="0.0.0.0", port=port, reload=False)
