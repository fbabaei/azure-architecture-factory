"""Integration tests for Order Service API."""
# pyright: reportMissingImports=false
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'order-service'))

# Mock environment variables
os.environ['APPLICATIONINSIGHTS_CONNECTION_STRING'] = 'InstrumentationKey=test-key'
os.environ['SERVICE_NAME'] = 'order-service'

from main import app

client = TestClient(app)


def test_health_endpoint():
    """Test service health check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "order-service"


def test_create_order():
    """Test order creation via API."""
    payload = {
        "customer_id": "cust-456",
        "items": [
            {"sku": "SKU-001", "quantity": 1, "unit_price": 99.99}
        ],
        "total_amount": 99.99
    }
    response = client.post("/api/v1/orders", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust-456"
    assert data["status"] == "CREATED"
    assert "order_id" in data


def test_get_order():
    """Test retrieve order."""
    # First create an order
    payload = {
        "customer_id": "cust-789",
        "items": [
            {"sku": "SKU-002", "quantity": 2, "unit_price": 50.00}
        ],
        "total_amount": 100.00
    }
    create_response = client.post("/api/v1/orders", json=payload)
    order_id = create_response.json()["order_id"]
    
    # Then retrieve it
    get_response = client.get(f"/api/v1/orders/{order_id}")
    assert get_response.status_code == 200
    assert get_response.json()["order_id"] == order_id


def test_list_orders():
    """Test listing orders."""
    response = client.get("/api/v1/orders")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "orders" in data


def test_get_nonexistent_order():
    """Test getting non-existent order returns 404."""
    response = client.get("/api/v1/orders/nonexistent-id")
    assert response.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=src', '--cov-report=term-missing'])
