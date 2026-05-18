"""Shared library package for OrderManagement Platform microservices."""
from .models import (
    Order, OrderItem, OrderStatus,
    Payment, PaymentStatus,
    Notification, NotificationType, NotificationStatus,
    AnalyticsMetric,
    ServiceBusEvent
)
from .telemetry import TelemetryClient, get_telemetry_client, configure_logging
from .service_bus import (
    ServiceBusManager,
    get_service_bus_manager,
    publish_order_created,
    publish_payment_processed,
    publish_inventory_reserved,
)
from .resilience import (
    CircuitBreaker, CircuitBreakerException, circuit_breaker,
    retry_with_backoff, RateLimiter, HealthCheck, HealthCheckRegistry
)

__all__ = [
    # Models
    "Order", "OrderItem", "OrderStatus",
    "Payment", "PaymentStatus",
    "Notification", "NotificationType", "NotificationStatus",
    "AnalyticsMetric",
    "ServiceBusEvent",
    # Telemetry
    "TelemetryClient", "get_telemetry_client", "configure_logging",
    # Service Bus
    "ServiceBusManager", "get_service_bus_manager",
    "publish_order_created", "publish_payment_processed", "publish_inventory_reserved",
    # Resilience
    "CircuitBreaker", "CircuitBreakerException", "circuit_breaker",
    "retry_with_backoff", "RateLimiter", "HealthCheck", "HealthCheckRegistry"
]
