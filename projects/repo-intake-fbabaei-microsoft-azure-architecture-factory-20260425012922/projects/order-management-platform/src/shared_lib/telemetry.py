"""Telemetry and Application Insights instrumentation utilities."""
import logging
import os
from typing import Dict, Any, Optional
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace, metrics
from opentelemetry import baggage


class TelemetryClient:
    """Application Insights telemetry client for distributed tracing and metrics."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelemetryClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if TelemetryClient._initialized:
            return
        
        self.connection_string = os.getenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "InstrumentationKey=00000000-0000-0000-0000-000000000000"
        )
        self.service_name = os.getenv("SERVICE_NAME", "order-management-service")
        self.environment = os.getenv("ENVIRONMENT", "dev")
        
        # Configure Azure Monitor with OpenTelemetry
        try:
            configure_azure_monitor(
                connection_string=self.connection_string,
                service_name=self.service_name,
                service_version="1.0.0",
                environment=self.environment
            )
            logging.info(f"Telemetry configured for {self.service_name}")
        except Exception as e:
            logging.error(f"Failed to configure telemetry: {e}")

        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)

        self.order_counter = self.meter.create_counter(
            "order.created",
            description="Number of orders created",
            unit="1"
        )
        self.payment_counter = self.meter.create_counter(
            "payment.processed",
            description="Number of payments processed",
            unit="1"
        )
        self.error_counter = self.meter.create_counter(
            "errors.total",
            description="Total number of errors",
            unit="1"
        )
        self.request_histogram = self.meter.create_histogram(
            "http.request.duration",
            description="HTTP request duration",
            unit="ms"
        )

        TelemetryClient._initialized = True
    
    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Start a new span for distributed tracing."""
        span = self.tracer.start_span(name)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        return span
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID in baggage for distributed tracing."""
        baggage.set_baggage("correlation_id", correlation_id)
    
    def get_correlation_id(self) -> Optional[str]:
        """Get correlation ID from baggage."""
        return baggage.get_baggage("correlation_id")
    
    def record_order_created(self, order_id: str, amount: float):
        """Record order creation metric."""
        self.order_counter.add(1, {"order_id": order_id, "amount": amount})
    
    def record_payment_processed(self, payment_id: str, amount: float, status: str):
        """Record payment processing metric."""
        self.payment_counter.add(1, {"payment_id": payment_id, "status": status})
    
    def record_error(self, error_type: str, error_message: str):
        """Record error metric."""
        self.error_counter.add(1, {"error_type": error_type})
    
    def record_request_duration(self, duration_ms: float, endpoint: str, status_code: int):
        """Record HTTP request duration."""
        self.request_histogram.record(duration_ms, {"endpoint": endpoint, "status": status_code})


def get_telemetry_client() -> TelemetryClient:
    """Get or create the telemetry client singleton."""
    return TelemetryClient()


def configure_logging():
    """Configure structured logging for all services."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Filter out verbose logs from dependencies
    logging.getLogger("azure.core.pipeline.policies").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
