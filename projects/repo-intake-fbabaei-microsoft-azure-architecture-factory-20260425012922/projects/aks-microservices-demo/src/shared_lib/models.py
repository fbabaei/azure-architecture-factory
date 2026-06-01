from datetime import UTC, datetime
from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: str = "ok"
    service: str
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Product(BaseModel):
    sku: str
    name: str
    category: str
    description: str
    price: float
    in_stock: bool = True


class OrderLine(BaseModel):
    sku: str
    quantity: int = Field(gt=0)


class PaymentDetails(BaseModel):
    cardholder_name: str
    card_last4: str = Field(min_length=4, max_length=4)
    method: str = 'credit_card'


class OrderRequest(BaseModel):
    customer_id: str
    lines: list[OrderLine]
    payment: PaymentDetails


class OrderItemSummary(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_price: float
    line_total: float


class OrderRecord(BaseModel):
    order_id: str
    customer_id: str
    items: list[OrderItemSummary]
    subtotal: float
    tax: float
    total: float
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaymentAuthorizationRequest(BaseModel):
    order_id: str
    amount: float
    currency: str = 'USD'
    payment: PaymentDetails


class PaymentAuthorization(BaseModel):
    status: str
    transaction_id: str
    amount: float
    currency: str
    authorized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CheckoutResult(BaseModel):
    order: OrderRecord
    payment: PaymentAuthorization
    status: str
