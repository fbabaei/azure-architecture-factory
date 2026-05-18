"""Azure Service Bus event publisher and subscriber utilities."""
import asyncio
import json
import logging
import os
from typing import Callable, Dict, Any, Optional, Type
from azure.servicebus.aio import ServiceBusClient
from azure.identity.aio import DefaultAzureCredential
from .models import ServiceBusEvent


logger = logging.getLogger(__name__)


class ServiceBusManager:
    """Manages Azure Service Bus connections and message publishing/subscribing."""
    
    _instance = None
    _initialized = False
    
    # Event topic names
    EVENTS = {
        "ORDER_CREATED": "OrderCreated",
        "ORDER_CANCELLED": "OrderCancelled",
        "PAYMENT_PROCESSED": "PaymentProcessed",
        "PAYMENT_FAILED": "PaymentFailed",
        "INVENTORY_RESERVED": "InventoryReserved",
        "INVENTORY_RELEASED": "InventoryReleased",
        "NOTIFICATION_SENT": "NotificationSent"
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceBusManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if ServiceBusManager._initialized:
            return
        
        self.namespace_url = os.getenv("SERVICE_BUS_NAMESPACE_URL")
        if not self.namespace_url:
            raise ValueError("SERVICE_BUS_NAMESPACE_URL environment variable not set")
        
        self.client: Optional[ServiceBusClient] = None
        self.credential: Optional[DefaultAzureCredential] = None
        self._subscribers: Dict[str, list] = {}
        ServiceBusManager._initialized = True
    
    async def initialize(self):
        """Initialize the Service Bus client with managed identity."""
        try:
            self.credential = DefaultAzureCredential()
            self.client = ServiceBusClient(
                fully_qualified_namespace=self.namespace_url,
                credential=self.credential
            )
            logger.info(f"Service Bus client initialized for {self.namespace_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Service Bus client: {e}")
            raise
    
    async def publish_event(self, topic_name: str, event: ServiceBusEvent):
        """Publish an event to a Service Bus topic."""
        if not self.client:
            await self.initialize()
        
        try:
            async with self.client.get_topic_sender(topic_name=topic_name) as sender:
                message_body = event.to_json()
                from azure.servicebus import ServiceBusMessage
                message = ServiceBusMessage(
                    body=message_body,
                    content_type="application/json"
                )
                # Add custom properties for correlation
                message.application_properties = {
                    "correlation_id": event.correlation_id,
                    "event_type": event.event_type
                }
                await sender.send_messages(message)
                logger.info(f"Event published: {event.event_type} to {topic_name}")
        except Exception as e:
            logger.error(f"Failed to publish event to {topic_name}: {e}")
            raise
    
    async def subscribe_to_topic(
        self,
        topic_name: str,
        subscription_name: str,
        handler: Callable[[ServiceBusEvent], Any],
        event_type: Optional[Type] = None
    ):
        """Subscribe to a Service Bus topic and process messages with a handler."""
        if not self.client:
            await self.initialize()
        
        try:
            async with self.client.get_subscription_receiver(
                topic_name=topic_name,
                subscription_name=subscription_name,
                max_wait_time=60  # Maximum wait for new messages
            ) as receiver:
                logger.info(f"Subscribed to {topic_name}/{subscription_name}")
                
                async for message in receiver:
                    try:
                        # Parse event from message body
                        body = json.loads(str(message))
                        event = ServiceBusEvent(
                            event_type=body.get("event_type"),
                            correlation_id=body.get("correlation_id"),
                            payload=body.get("payload", {})
                        )
                        
                        # Call handler
                        result = handler(event)
                        if asyncio.iscoroutine(result):
                            await result
                        
                        # Complete the message
                        await receiver.complete_message(message)
                        logger.info(f"Message processed: {event.event_type}")
                    
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        # Move to dead-letter queue after max deliveries
                        await receiver.dead_letter_message(message)
        
        except Exception as e:
            logger.error(f"Subscription error for {topic_name}/{subscription_name}: {e}")
            raise
    
    async def close(self):
        """Close the Service Bus client."""
        if self.client:
            await self.client.close()
            logger.info("Service Bus client closed")


def get_service_bus_manager() -> ServiceBusManager:
    """Get or create the Service Bus manager singleton."""
    return ServiceBusManager()


async def publish_order_created(order_id: str, customer_id: str, total_amount: float, correlation_id: str):
    """Publish an OrderCreated event."""
    manager = get_service_bus_manager()
    event = ServiceBusEvent(
        event_type="OrderCreated",
        correlation_id=correlation_id,
        payload={
            "order_id": order_id,
            "customer_id": customer_id,
            "total_amount": total_amount
        }
    )
    await manager.publish_event(ServiceBusManager.EVENTS["ORDER_CREATED"], event)


async def publish_payment_processed(order_id: str, payment_id: str, status: str, correlation_id: str):
    """Publish a PaymentProcessed event."""
    manager = get_service_bus_manager()
    event = ServiceBusEvent(
        event_type="PaymentProcessed",
        correlation_id=correlation_id,
        payload={
            "order_id": order_id,
            "payment_id": payment_id,
            "status": status
        }
    )
    await manager.publish_event(ServiceBusManager.EVENTS["PAYMENT_PROCESSED"], event)


async def publish_inventory_reserved(order_id: str, sku: str, quantity: int, correlation_id: str):
    """Publish an InventoryReserved event."""
    manager = get_service_bus_manager()
    event = ServiceBusEvent(
        event_type="InventoryReserved",
        correlation_id=correlation_id,
        payload={
            "order_id": order_id,
            "sku": sku,
            "quantity": quantity
        }
    )
    await manager.publish_event(ServiceBusManager.EVENTS["INVENTORY_RESERVED"], event)
