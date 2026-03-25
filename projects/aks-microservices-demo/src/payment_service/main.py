from uuid import uuid4

from fastapi import FastAPI

from shared_lib import HealthStatus, PaymentAuthorization, PaymentAuthorizationRequest, get_settings


app = FastAPI(title="AKS Demo - Payment Service")
settings = get_settings()


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(service="payment-service", environment=settings.environment)


@app.post("/authorize", response_model=PaymentAuthorization)
def authorize_payment(payload: PaymentAuthorizationRequest) -> PaymentAuthorization:
    status = "authorized" if payload.amount <= 10000 else "manual_review"
    return PaymentAuthorization(
        status=status,
        transaction_id=f"tx-{uuid4().hex[:10]}",
        amount=payload.amount,
        currency=payload.currency,
    )
