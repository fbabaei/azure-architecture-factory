"""Configuration and fixtures for tests."""
import pytest
import os

# Configure test environment
os.environ['ENVIRONMENT'] = 'test'
os.environ['SERVICE_NAME'] = 'order-management-test'
os.environ['APPLICATIONINSIGHTS_CONNECTION_STRING'] = 'InstrumentationKey=test-key'


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return {
        "test_user_id": "test-user-123",
        "test_order_id": "test-order-456",
        "api_base_url": "http://localhost:8000"
    }


@pytest.fixture
def mock_handler():
    """Provide mock event handler for testing."""
    def _mock_handler(event):
        return {"processed": True, "event": event.event_type}
    return _mock_handler
