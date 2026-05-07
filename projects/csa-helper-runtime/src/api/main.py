"""FastAPI wrapper exposing the csa-helper agent-framework over HTTP.

Per BRD FR-3: do NOT modify build_team.py. We import it from a vendored
copy of the csa-helper repo placed at /app/csa_helper at Docker build
time. The wrapper only adds:
  - POST /ask      -> Team.ask(prompt) -> {answer, trace}
  - GET  /health   -> liveness
  - GET  /health/ready -> readiness (verifies env + AOAI client init)
  - One Application Insights custom event per /ask call (FR-6).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# The vendored csa-helper repo is mounted at /app/csa_helper inside the image.
# Add the repo root to sys.path so `from agent_framework.build_team import build_team`
# resolves relative to it (build_team.py uses REPO = Path(__file__).parent.parent).
CSA_HELPER_ROOT = Path(os.environ.get("CSA_HELPER_ROOT", "/app/csa_helper"))
if str(CSA_HELPER_ROOT) not in sys.path:
    sys.path.insert(0, str(CSA_HELPER_ROOT))

# Import lazily inside startup so /health stays cheap and the import error
# surfaces in /health/ready instead of crashing the worker on boot.
_team: Any = None
_team_init_error: Exception | None = None

logger = logging.getLogger("csa_helper_runtime")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

# Application Insights wiring — only enabled when connection string is set.
_telemetry_enabled = False
try:
    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        from opencensus.ext.azure.log_exporter import AzureEventHandler

        event_logger = logging.getLogger("csa_ask_events")
        event_logger.setLevel(logging.INFO)
        event_logger.addHandler(
            AzureEventHandler(
                connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
            )
        )
        _telemetry_enabled = True
    else:
        event_logger = logging.getLogger("csa_ask_events")
except Exception as exc:  # pragma: no cover - telemetry is best-effort
    logger.warning("App Insights wiring failed: %s", exc)
    event_logger = logging.getLogger("csa_ask_events")


app = FastAPI(title="CSA Helper Runtime", version="1.0.0")


class AskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)


class AskResponse(BaseModel):
    answer: str
    trace: list[dict]


def _init_team() -> Any:
    """Lazy-init the orchestrator team. Raises on misconfig."""
    global _team, _team_init_error
    if _team is not None:
        return _team
    if _team_init_error is not None:
        raise _team_init_error
    try:
        from agent_framework.build_team import build_team  # type: ignore

        _team = build_team()
        return _team
    except Exception as exc:  # noqa: BLE001
        _team_init_error = exc
        raise


@app.on_event("startup")
def _startup() -> None:
    # Best-effort warmup; failures are surfaced via /health/ready, not boot.
    try:
        _init_team()
        logger.info("csa-helper team initialized")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Team init deferred: %s", exc)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready() -> dict[str, Any]:
    required = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise HTTPException(status_code=503, detail={"missing_env": missing})
    try:
        _init_team()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"team_init": str(exc)})
    return {"status": "ready", "telemetry": _telemetry_enabled}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    try:
        team = _init_team()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail={"team_init": str(exc)})

    started = time.perf_counter()
    try:
        answer, trace = team.ask(req.prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ask() failed")
        raise HTTPException(status_code=500, detail={"error": str(exc)})
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    # FR-6 custom event — best-effort.
    try:
        event_logger.info(
            "ask",
            extra={
                "custom_dimensions": {
                    "prompt_chars": len(req.prompt),
                    "specialist_count": len({h.get("agent") for h in trace if h.get("agent")}),
                    "tool_hops": len(trace),
                    "latency_ms": elapsed_ms,
                    "model_deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
                }
            },
        )
    except Exception as exc:  # pragma: no cover - telemetry is best-effort
        logger.warning("event emit failed: %s", exc)

    return AskResponse(answer=answer, trace=trace)
