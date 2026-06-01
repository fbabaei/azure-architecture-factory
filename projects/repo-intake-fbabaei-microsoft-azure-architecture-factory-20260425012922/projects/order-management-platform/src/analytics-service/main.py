"""Analytics Service - Order metrics and KPIs."""
import os
import sys
import logging
from datetime import datetime, UTC
from fastapi import FastAPI
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared_lib import AnalyticsMetric, TelemetryClient, configure_logging, HealthCheckRegistry, HealthCheck

configure_logging()
logger = logging.getLogger(__name__)
telemetry = TelemetryClient()

app = FastAPI(title="Analytics Service", version="1.0.0")

# In-memory metrics store (replace with Cosmos DB in production)
metrics_db = {}


class AnalyticsServiceHealthCheck(HealthCheck):
    async def check(self) -> bool:
        return True
    def name(self) -> str:
        return "analytics-service"


health_registry = HealthCheckRegistry()
health_registry.register(AnalyticsServiceHealthCheck())


@app.get("/health")
async def health():
    return JSONResponse(status_code=200, content={"status": "healthy", "service": "analytics-service"})


@app.get("/api/v1/analytics/orders/daily")
async def get_daily_orders(date: str = None):
    """Get daily order metrics."""
    if not date:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
    
    metric = metrics_db.get(date, AnalyticsMetric(date=date))
    
    return {
        "date": metric.date,
        "orders_created": metric.orders_created,
        "orders_cancelled": metric.orders_cancelled,
        "avg_order_value": metric.avg_order_value
    }


@app.get("/api/v1/analytics/payments/success-rate")
async def get_payment_success_rate():
    """Get payment success rate."""
    total_payments = 0
    successful_payments = 0
    
    for metric in metrics_db.values():
        total_payments += metric.payments_success + metric.payments_failed
        successful_payments += metric.payments_success
    
    success_rate = (successful_payments / total_payments * 100) if total_payments > 0 else 0
    
    return {
        "success_rate": success_rate,
        "successful": successful_payments,
        "total": total_payments
    }


@app.get("/api/v1/analytics/inventory/turnover")
async def get_inventory_turnover():
    """Get inventory metrics."""
    total_reserved = sum(m.inventory_reserved for m in metrics_db.values())
    total_orders = sum(m.orders_created for m in metrics_db.values())
    
    return {
        "total_reserved": total_reserved,
        "total_orders": total_orders,
        "turnover_ratio": total_reserved / total_orders if total_orders > 0 else 0
    }


@app.get("/api/v1/analytics/summary")
async def get_analytics_summary():
    """Get analytics summary."""
    total_orders = sum(m.orders_created for m in metrics_db.values())
    total_notifications = sum(m.notifications_sent for m in metrics_db.values())
    
    return {
        "total_orders": total_orders,
        "total_notifications": total_notifications,
        "dates_covered": len(metrics_db),
        "average_order_value": sum(m.avg_order_value for m in metrics_db.values()) / len(metrics_db) if metrics_db else 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005, log_level="info")
