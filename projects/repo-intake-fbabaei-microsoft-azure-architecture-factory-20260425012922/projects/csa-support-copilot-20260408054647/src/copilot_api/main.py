from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .config import load_settings
from .models import AskRequest, AskResponse, ToolCatalogResponse, ToolSummary
from .rate_limit import SlidingWindowRateLimiter
from .security import require_api_access
from .services.copilot_service import build_response


settings = load_settings()
rate_limiter = SlidingWindowRateLimiter(limit=settings.rate_limit_per_minute)


def _docs_enabled() -> bool:
    return settings.app_env.lower() in {"dev", "local"}


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if _docs_enabled() else None,
    redoc_url="/redoc" if _docs_enabled() else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "env": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready() -> dict:
    if settings.require_api_key and not settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not configured with CSA_API_KEYS.",
        )
    return {
        "status": "ready",
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/copilot/tools", response_model=ToolCatalogResponse)
def list_tools(_: None = Depends(require_api_access)) -> ToolCatalogResponse:
    return ToolCatalogResponse(
        tools=[
            ToolSummary(
                name="kb-search",
                description="Searches approved CSA knowledge and policy content.",
            ),
            ToolSummary(
                name="runbook-assistant",
                description="Returns step-by-step operational runbook guidance.",
            ),
        ]
    )


@app.post("/api/copilot/ask", response_model=AskResponse)
def ask_copilot(
    payload: AskRequest,
    request: Request,
    _: None = Depends(require_api_access),
) -> AskResponse:
    request_key = payload.user_id
    if not request_key:
        request_key = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(request_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry in one minute.",
        )

    guidance, tools_used, citations = build_response(payload.question, payload.context)
    return AskResponse(
        answer=guidance,
        source="csa-support-mcp-v1",
        request_id=request.state.request_id,
        tools_used=tools_used,
        citations=citations,
    )
