from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared_lib import HealthStatus, OrderItemSummary, OrderRecord, OrderRequest, get_settings


app = FastAPI(title="AKS Demo - Order Service")
settings = get_settings()

PRODUCT_CATALOG = {
    "SKU-1001": {"name": "Kubernetes Handbook", "price": 49.0},
    "SKU-1002": {"name": "Platform SRE Guide", "price": 79.0},
    "SKU-1003": {"name": "Cloud Native Patterns", "price": 59.0},
    "SKU-1004": {"name": "AKS Cost Dashboard", "price": 129.0},
}

ORDERS: dict[str, OrderRecord] = {}


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(service="order-service", environment=settings.environment)


@app.post("/orders", response_model=OrderRecord)
def create_order(payload: OrderRequest) -> OrderRecord:
    items: list[OrderItemSummary] = []
    subtotal = 0.0

    for line in payload.lines:
        catalog_item = PRODUCT_CATALOG.get(line.sku)
        if catalog_item is None:
            raise HTTPException(status_code=400, detail=f"Unknown SKU: {line.sku}")

        line_total = catalog_item["price"] * line.quantity
        subtotal += line_total
        items.append(
            OrderItemSummary(
                sku=line.sku,
                name=catalog_item["name"],
                quantity=line.quantity,
                unit_price=catalog_item["price"],
                line_total=line_total,
            )
        )

    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)
    order = OrderRecord(
        order_id=f"ord-{uuid4().hex[:8]}",
        customer_id=payload.customer_id,
        items=items,
        subtotal=round(subtotal, 2),
        tax=tax,
        total=total,
        status="accepted",
    )
    ORDERS[order.order_id] = order
    return order


@app.get("/orders/{order_id}", response_model=OrderRecord)
def get_order(order_id: str) -> OrderRecord:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
