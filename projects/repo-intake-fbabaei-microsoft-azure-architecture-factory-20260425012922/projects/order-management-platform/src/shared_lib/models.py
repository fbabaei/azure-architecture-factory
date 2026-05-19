"""Shared data models for all microservices."""
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
import json


def utc_now() -> datetime:
    return datetime.now(UTC)


class OrderStatus(str, Enum):
    """Order status enumeration."""
    CREATED = "CREATED"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    CANCELLED = "CANCELLED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class NotificationType(str, Enum):
    """Notification type enumeration."""
    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class NotificationStatus(str, Enum):
    """Notification delivery status."""
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"


@dataclass
class OrderItem:
    """Individual item in an order."""
    sku: str
    quantity: int
    unit_price: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.sku,
            "quantity": self.quantity,
            "unit_price": self.unit_price
        }


@dataclass
class Order:
    """Order domain model."""
    customer_id: str
    items: List[OrderItem]
    total_amount: float
    status: OrderStatus = OrderStatus.CREATED
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "items": [item.to_dict() for item in self.items],
            "total_amount": self.total_amount,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "correlation_id": self.correlation_id,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class Payment:
    """Payment domain model."""
    order_id: str
    amount: float
    payment_method: str
    status: PaymentStatus = PaymentStatus.PENDING
    payment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "payment_id": self.payment_id,
            "order_id": self.order_id,
            "amount": self.amount,
            "payment_method": self.payment_method,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "correlation_id": self.correlation_id,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class Notification:
    """Notification domain model."""
    recipient: str
    notification_type: NotificationType
    subject: str
    body: str
    order_id: Optional[str] = None
    status: NotificationStatus = NotificationStatus.PENDING
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    sent_at: Optional[datetime] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "recipient": self.recipient,
            "notification_type": self.notification_type.value,
            "subject": self.subject,
            "body": self.body,
            "order_id": self.order_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "correlation_id": self.correlation_id
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class AnalyticsMetric:
    """Analytics metric model."""
    date: str  # YYYY-MM-DD
    orders_created: int = 0
    orders_cancelled: int = 0
    payments_success: int = 0
    payments_failed: int = 0
    inventory_reserved: int = 0
    notifications_sent: int = 0
    avg_order_value: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "orders_created": self.orders_created,
            "orders_cancelled": self.orders_cancelled,
            "payments_success": self.payments_success,
            "payments_failed": self.payments_failed,
            "inventory_reserved": self.inventory_reserved,
            "notifications_sent": self.notifications_sent,
            "avg_order_value": self.avg_order_value
        }


class ServiceBusEvent:
    """Base class for Service Bus events."""
    
    def __init__(self, event_type: str, correlation_id: str, payload: Dict[str, Any]):
        self.event_type = event_type
        self.correlation_id = correlation_id
        self.payload = payload
        self.timestamp = utc_now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "timestamp": self.timestamp
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
