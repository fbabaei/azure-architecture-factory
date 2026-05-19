"""Notification Service - Email/SMS notifications."""
import os
import sys
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared_lib import Notification, NotificationStatus, TelemetryClient, configure_logging, HealthCheckRegistry, HealthCheck

configure_logging()
logger = logging.getLogger(__name__)
telemetry = TelemetryClient()

app = FastAPI(title="Notification Service", version="1.0.0")
notifications_db = {}


class NotificationServiceHealthCheck(HealthCheck):
    async def check(self) -> bool:
        return True
    def name(self) -> str:
        return "notification-service"


health_registry = HealthCheckRegistry()
health_registry.register(NotificationServiceHealthCheck())


@app.get("/health")
async def health():
    return JSONResponse(status_code=200, content={"status": "healthy", "service": "notification-service"})


@app.post("/api/v1/notifications")
async def send_notification(request: dict):
    """Send notification."""
    notification = Notification(
        recipient=request.get("recipient"),
        notification_type=request.get("notification_type"),
        subject=request.get("subject"),
        body=request.get("body"),
        order_id=request.get("order_id"),
        status=NotificationStatus.SENT
    )
    notifications_db[notification.notification_id] = notification
    logger.info(f"Notification sent: {notification.notification_id} to {notification.recipient}")
    
    return {"notification_id": notification.notification_id, "status": "SENT"}


@app.get("/api/v1/notifications/{notification_id}/status")
async def get_notification_status(notification_id: str):
    """Get notification status."""
    notification = notifications_db.get(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found")
    
    return {"notification_id": notification_id, "status": notification.status.value}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004, log_level="info")
