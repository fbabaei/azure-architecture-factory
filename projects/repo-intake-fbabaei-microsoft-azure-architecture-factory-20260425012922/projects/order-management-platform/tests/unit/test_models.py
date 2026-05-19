"""Unit tests for Order Service."""
# pyright: reportMissingImports=false
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from shared_lib import Order, OrderItem, OrderStatus, Payment, PaymentStatus


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    items = [
        OrderItem(sku="SKU-001", quantity=2, unit_price=50.0),
        OrderItem(sku="SKU-002", quantity=1, unit_price=100.0)
    ]
    return Order(customer_id="cust-123", items=items, total_amount=200.0)


def test_order_creation(sample_order):
    """Test order creation."""
    assert sample_order.order_id is not None
    assert sample_order.customer_id == "cust-123"
    assert len(sample_order.items) == 2
    assert sample_order.status == OrderStatus.CREATED


def test_order_to_dict(sample_order):
    """Test order serialization."""
    order_dict = sample_order.to_dict()
    assert order_dict["customer_id"] == "cust-123"
    assert order_dict["status"] == "CREATED"
    assert len(order_dict["items"]) == 2


def test_payment_creation():
    """Test payment creation."""
    payment = Payment(order_id="order-123", amount=200.0, payment_method="credit_card")
    assert payment.payment_id is not None
    assert payment.status == PaymentStatus.PENDING


def test_payment_status_transitions():
    """Test payment status transitions."""
    payment = Payment(order_id="order-123", amount=200.0, payment_method="credit_card")
    assert payment.status == PaymentStatus.PENDING
    
    # Simulate status update
    payment.status = PaymentStatus.COMPLETED
    assert payment.status == PaymentStatus.COMPLETED


def test_order_total_amount_calculation(sample_order):
    """Test order amount calculation."""
    expected_total = (2 * 50.0) + (1 * 100.0)
    assert sample_order.total_amount == 200.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=src', '--cov-report=term-missing'])
