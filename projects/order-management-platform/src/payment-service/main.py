"""Payment Service - Payment processing."""
import os
import sys
import logging
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared_lib import Payment, PaymentStatus, TelemetryClient, configure_logging, HealthCheckRegistry, HealthCheck

configure_logging()
logger = logging.getLogger(__name__)
telemetry = TelemetryClient()

app = FastAPI(title="Payment Service", version="1.0.0")
payments_db = {}


class ProcessPaymentRequest(BaseModel):
    order_id: str
    amount: float
    payment_method: str


class PaymentResponse(BaseModel):
    payment_id: str
    order_id: str
    amount: float
    status: str


class PaymentServiceHealthCheck(HealthCheck):
    async def check(self) -> bool:
        return True
    def name(self) -> str:
        return "payment-service"


health_registry = HealthCheckRegistry()
health_registry.register(PaymentServiceHealthCheck())


@app.get("/health")
async def health():
    return JSONResponse(status_code=200, content={"status": "healthy", "service": "payment-service"})


@app.post("/api/v1/payments")
async def process_payment(request: ProcessPaymentRequest):
    """Process payment."""
    payment = Payment(
        order_id=request.order_id,
        amount=request.amount,
        payment_method=request.payment_method,
        status=PaymentStatus.COMPLETED
    )
    payments_db[payment.payment_id] = payment
    telemetry.record_payment_processed(payment.payment_id, request.amount, "COMPLETED")
    logger.info(f"Payment processed: {payment.payment_id} for order {request.order_id}")
    
    return PaymentResponse(
        payment_id=payment.payment_id,
        order_id=request.order_id,
        amount=request.amount,
        status="COMPLETED"
    )


@app.get("/api/v1/payments/{payment_id}")
async def get_payment(payment_id: str):
    """Get payment details."""
    payment = payments_db.get(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    
    return PaymentResponse(
        payment_id=payment.payment_id,
        order_id=payment.order_id,
        amount=payment.amount,
        status=payment.status.value
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
