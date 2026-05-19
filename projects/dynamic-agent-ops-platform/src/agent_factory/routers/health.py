"""Health router."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    return JSONResponse({"status": "ready"})
