"""Inventory Service - Stock management."""
import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared_lib import TelemetryClient, configure_logging, HealthCheckRegistry, HealthCheck

configure_logging()
logger = logging.getLogger(__name__)
telemetry = TelemetryClient()

app = FastAPI(title="Inventory Service", version="1.0.0")

# In-memory inventory store (replace with SQL DB in production)
inventory_db = {
    "SKU-001": {"quantity": 100, "reserved": 0},
    "SKU-002": {"quantity": 50, "reserved": 0},
    "SKU-003": {"quantity": 200, "reserved": 0}
}


class InventoryStatusResponse(BaseModel):
    sku: str
    available: int
    reserved: int
    total: int


class ReserveInventoryRequest(BaseModel):
    sku: str
    quantity: int
    order_id: str


class InventoryServiceHealthCheck(HealthCheck):
    async def check(self) -> bool:
        return True
    def name(self) -> str:
        return "inventory-service"


health_registry = HealthCheckRegistry()
health_registry.register(InventoryServiceHealthCheck())


@app.get("/health")
async def health():
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "service": "inventory-service"}
    )


@app.get("/api/v1/inventory/{sku}/available")
async def check_availability(sku: str, x_correlation_id: str = Header(None)):
    """Check stock availability."""
    if sku not in inventory_db:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found")
    
    stock = inventory_db[sku]
    available = stock["quantity"] - stock["reserved"]
    
    return InventoryStatusResponse(
        sku=sku,
        available=available,
        reserved=stock["reserved"],
        total=stock["quantity"]
    )


@app.post("/api/v1/inventory/{sku}/reserve")
async def reserve_inventory(sku: str, request: ReserveInventoryRequest):
    """Reserve inventory for order."""
    if sku not in inventory_db:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found")
    
    stock = inventory_db[sku]
    available = stock["quantity"] - stock["reserved"]
    
    if available < request.quantity:
        raise HTTPException(status_code=409, detail="Insufficient stock")
    
    stock["reserved"] += request.quantity
    logger.info(f"Reserved {request.quantity} units of {sku} for order {request.order_id}")
    
    return {"sku": sku, "reserved": request.quantity, "order_id": request.order_id}


@app.post("/api/v1/inventory/{sku}/release")
async def release_inventory(sku: str, request: dict):
    """Release reservation."""
    if sku not in inventory_db:
        raise HTTPException(status_code=404, detail=f"SKU {sku} not found")
    
    quantity = request.get("quantity", 0)
    inventory_db[sku]["reserved"] = max(0, inventory_db[sku]["reserved"] - quantity)
    
    return {"sku": sku, "released": quantity}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
