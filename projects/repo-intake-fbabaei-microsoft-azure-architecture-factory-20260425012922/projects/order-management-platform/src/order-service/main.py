"""Order Service - Core order management."""
import os
import sys
import logging
from datetime import datetime
from typing import List
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared_lib import (
    Order, OrderItem, OrderStatus,
    TelemetryClient, configure_logging,
    HealthCheckRegistry, HealthCheck,
    publish_order_created
)

configure_logging()
logger = logging.getLogger(__name__)
telemetry = TelemetryClient()

app = FastAPI(title="Order Service", version="1.0.0")

# In-memory store for demo (replace with Cosmos DB in production)
orders_db: dict[str, Order] = {}


class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[dict]
    total_amount: float


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    items: list
    total_amount: float
    status: str
    created_at: str


class OrderServiceHealthCheck(HealthCheck):
    """Health check for Order Service."""
    
    async def check(self) -> bool:
        return True
    
    def name(self) -> str:
        return "order-service"


health_registry = HealthCheckRegistry()
health_registry.register(OrderServiceHealthCheck())


def get_correlation_id(x_correlation_id: str = Header(None)) -> str:
    return x_correlation_id or telemetry.get_correlation_id() or "no-correlation"


@app.get("/health")
async def health():
    """Health check endpoint."""
    is_healthy = await health_registry.is_healthy()
    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content={"status": "healthy" if is_healthy else "degraded", "service": "order-service"}
    )


@app.post("/api/v1/orders")
async def create_order(
    request: CreateOrderRequest,
    correlation_id: str = Depends(get_correlation_id)
) -> OrderResponse:
    """Create a new order."""
    try:
        telemetry.set_correlation_id(correlation_id)
        
        # Create order items
        items = [OrderItem(sku=item["sku"], quantity=item["quantity"], unit_price=item["unit_price"]) 
                 for item in request.items]
        
        # Create order
        order = Order(
            customer_id=request.customer_id,
            items=items,
            total_amount=request.total_amount,
            correlation_id=correlation_id
        )
        
        # Store in "database"
        orders_db[order.order_id] = order
        
        # Publish event
        # await publish_order_created(order.order_id, order.customer_id, order.total_amount, correlation_id)
        
        telemetry.record_order_created(order.order_id, order.total_amount)
        
        logger.info(f"Order created: {order.order_id}")
        
        return OrderResponse(
            order_id=order.order_id,
            customer_id=order.customer_id,
            items=[item.to_dict() for item in order.items],
            total_amount=order.total_amount,
            status=order.status.value,
            created_at=order.created_at.isoformat()
        )
    except Exception as e:
        telemetry.record_error("ORDER_CREATE_ERROR", str(e))
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str, correlation_id: str = Depends(get_correlation_id)) -> OrderResponse:
    """Get order by ID."""
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    
    return OrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        items=[item.to_dict() for item in order.items],
        total_amount=order.total_amount,
        status=order.status.value,
        created_at=order.created_at.isoformat()
    )


@app.get("/api/v1/orders")
async def list_orders(skip: int = 0, limit: int = 10):
    """List all orders."""
    orders_list = list(orders_db.values())[skip:skip + limit]
    return {
        "total": len(orders_db),
        "orders": [
            OrderResponse(
                order_id=o.order_id,
                customer_id=o.customer_id,
                items=[item.to_dict() for item in o.items],
                total_amount=o.total_amount,
                status=o.status.value,
                created_at=o.created_at.isoformat()
            ).model_dump() for o in orders_list
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
