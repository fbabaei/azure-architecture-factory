"""API Gateway Service - Request routing and rate limiting."""
import os
import json
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional
import jwt
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import sys

# Add src root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared_lib import TelemetryClient, configure_logging, RateLimiter, HealthCheckRegistry, HealthCheck

# Initialize logging and telemetry
configure_logging()
logger = logging.getLogger(__name__)
telemetry = TelemetryClient()

app = FastAPI(title="API Gateway", version="1.0.0")


def _get_allowed_origins() -> list[str]:
    """Read allowed CORS origins from env without defaulting to wildcard."""
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or ["http://localhost:3000"]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SERVICE_REGISTRY = {
    "orders": os.getenv("ORDER_SERVICE_URL", "http://order-service:8001"),
    "inventory": os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8002"),
    "payments": os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8003"),
    "analytics": os.getenv("ANALYTICS_SERVICE_URL", "http://analytics-service:8005"),
}

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ENABLE_DEMO_AUTH_TOKEN_ENDPOINT = os.getenv("ENABLE_DEMO_AUTH_TOKEN_ENDPOINT", "false").lower() == "true"

if not JWT_SECRET:
    logger.warning("JWT_SECRET is not configured; authenticated endpoints will reject requests.")

# Rate limiters per user (simplified for demo)
rate_limiters = {}
MAX_REQUESTS_PER_MINUTE = 100


class APIGatewayHealthCheck(HealthCheck):
    """Health check for API Gateway."""
    
    async def check(self) -> bool:
        """Check if gateway is healthy."""
        # Check if we can reach other services
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                for service_name, service_url in SERVICE_REGISTRY.items():
                    health_url = f"{service_url}/health"
                    response = await client.get(health_url)
                    if response.status_code != 200:
                        logger.warning(f"Service {service_name} unhealthy")
                        return False
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def name(self) -> str:
        return "api-gateway"


# Register health checks
health_registry = HealthCheckRegistry()
health_registry.register(APIGatewayHealthCheck())


def validate_jwt_token(token: Optional[str] = Header(None, alias="Authorization")) -> dict:
    """Validate JWT token from Authorization header."""
    if not JWT_SECRET:
        raise HTTPException(status_code=503, detail="JWT configuration missing")

    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    
    # Remove 'Bearer ' prefix if present
    if token.startswith("Bearer "):
        token = token[7:]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_rate_limiter(user_id: str) -> RateLimiter:
    """Get or create rate limiter for user."""
    if user_id not in rate_limiters:
        rate_limiters[user_id] = RateLimiter(rate=MAX_REQUESTS_PER_MINUTE, per_seconds=60)
    return rate_limiters[user_id]


async def rate_limit_check(token_data: dict = Depends(validate_jwt_token)):
    """Check rate limit for user."""
    user_id = token_data.get("sub", "anonymous")
    limiter = get_rate_limiter(user_id)
    
    if not limiter.allow():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return user_id


@app.get("/health")
async def health():
    """Health check endpoint."""
    is_healthy = await health_registry.is_healthy()
    status = "healthy" if is_healthy else "degraded"
    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content={"status": status, "service": "api-gateway"}
    )


@app.get("/health/ready")
async def readiness():
    """Readiness check endpoint."""
    checks = await health_registry.check_all()
    is_ready = all(checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"ready": is_ready, "checks": checks}
    )


@app.post("/auth/token")
async def auth_token(request: Request):
    """Generate JWT token for testing/demo."""
    if not ENABLE_DEMO_AUTH_TOKEN_ENDPOINT:
        raise HTTPException(status_code=404, detail="Endpoint not enabled")

    if not JWT_SECRET:
        raise HTTPException(status_code=503, detail="JWT configuration missing")

    body = await request.json()
    user_id = body.get("user_id", "demo-user")
    
    payload = {
        "sub": user_id,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=24)
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


@app.api_route("/api/v1/orders/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/v1/orders", methods=["GET", "POST"])
async def proxy_orders(
    request: Request,
    path: str = "",
    user_id: str = Depends(rate_limit_check)
):
    """Proxy requests to Order Service."""
    started_at = datetime.now(UTC)
    correlation_id = request.headers.get("X-Correlation-ID", str(telemetry.tracer))
    telemetry.set_correlation_id(correlation_id)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{SERVICE_REGISTRY['orders']}/api/v1/orders/{path}".rstrip('/')
        
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers={"X-Correlation-ID": correlation_id},
                content=await request.body()
            )
            
            telemetry.record_request_duration(
                duration_ms=(datetime.now(UTC) - started_at).total_seconds() * 1000,
                endpoint="/api/v1/orders",
                status_code=response.status_code
            )
            
            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )
        except httpx.HTTPError as e:
            telemetry.record_error("HTTP_ERROR", str(e))
            raise HTTPException(status_code=503, detail="Order Service unavailable")


@app.api_route("/api/v1/inventory/{path:path}", methods=["GET", "POST"])
@app.api_route("/api/v1/inventory", methods=["GET"])
async def proxy_inventory(
    request: Request,
    path: str = "",
    user_id: str = Depends(rate_limit_check)
):
    """Proxy requests to Inventory Service."""
    correlation_id = request.headers.get("X-Correlation-ID", str(telemetry.tracer))
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{SERVICE_REGISTRY['inventory']}/api/v1/inventory/{path}".rstrip('/')
        
        try:
            response = await client.request(
                method=request.method,
                url=url,
                headers={"X-Correlation-ID": correlation_id},
                content=await request.body()
            )
            
            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="Inventory Service unavailable")


@app.api_route("/api/v1/analytics/{path:path}", methods=["GET"])
@app.api_route("/api/v1/analytics", methods=["GET"])
async def proxy_analytics(
    request: Request,
    path: str = "",
    user_id: str = Depends(rate_limit_check)
):
    """Proxy requests to Analytics Service."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{SERVICE_REGISTRY['analytics']}/api/v1/analytics/{path}".rstrip('/')
        
        try:
            response = await client.request(
                method=request.method,
                url=url,
                content=await request.body()
            )
            
            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="Analytics Service unavailable")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
