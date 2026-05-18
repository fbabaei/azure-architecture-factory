from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from shared_lib import CheckoutResult, HealthStatus, OrderRecord, OrderRequest, PaymentAuthorizationRequest, get_settings


app = FastAPI(title="AKS Demo - API Gateway")
settings = get_settings()
template_env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / 'templates'),
    autoescape=select_autoescape(['html', 'xml']),
)


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(service=settings.service_name, environment=settings.environment)


@app.get("/", response_class=HTMLResponse)
def storefront() -> HTMLResponse:
    template = template_env.get_template('index.html')
    return HTMLResponse(template.render(environment=settings.environment))


@app.get("/topology")
def topology() -> dict:
    endpoints = settings.endpoints()
    return {
        "gateway": "api-gateway",
        "services": {
            "catalog": endpoints.catalog_url,
            "order": endpoints.order_url,
            "payment": endpoints.payment_url,
        },
    }


@app.get("/products")
async def products() -> dict:
    endpoints = settings.endpoints()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{endpoints.catalog_url}/products")
        response.raise_for_status()
        return {"products": response.json()}


@app.post("/checkout", response_model=CheckoutResult)
async def checkout(payload: OrderRequest) -> CheckoutResult:
    endpoints = settings.endpoints()
    async with httpx.AsyncClient(timeout=5.0) as client:
        order_response = await client.post(f"{endpoints.order_url}/orders", json=payload.model_dump())
        order_response.raise_for_status()
        order: OrderRecord = OrderRecord.model_validate(order_response.json())
        payment_response = await client.post(
            f"{endpoints.payment_url}/authorize",
            json=PaymentAuthorizationRequest(
                order_id=order.order_id,
                amount=order.total,
                currency='USD',
                payment=payload.payment,
            ).model_dump(),
        )
        payment_response.raise_for_status()
        payment = payment_response.json()

    return CheckoutResult(order=order, payment=payment, status='completed')
