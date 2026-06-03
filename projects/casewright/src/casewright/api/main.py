"""Casewright FastAPI application entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from casewright.api.routers import agentic_chat, chat, health, pipeline, sharepoint
from casewright.core.observability import configure_telemetry

logging.basicConfig(level=logging.INFO)

# Opt-in distributed tracing + metrics (no-op without an App Insights connection string).
configure_telemetry("casewright-api")

app = FastAPI(
    title="Casewright API",
    description="Agentic case knowledge platform — grounded RAG chat + ingestion orchestration.",
    version="1.0.0",
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(agentic_chat.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(sharepoint.router, prefix="/api")

# Minimal built-in chat client (served only if the static assets are present).
_web_dir = Path(__file__).resolve().parent.parent / "web"
if _web_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dir), html=True), name="web")
