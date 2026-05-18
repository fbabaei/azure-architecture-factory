import unittest
from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PROJECT_SRC))

from api_gateway.main import app as gateway_app  # noqa: E402
from catalog_service.main import app as catalog_app  # noqa: E402
from order_service.main import app as order_app  # noqa: E402
from payment_service.main import app as payment_app  # noqa: E402


class ServiceHealthTests(unittest.TestCase):
    def _assert_health(self, app):
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_api_gateway_health(self):
        self._assert_health(gateway_app)

    def test_catalog_health(self):
        self._assert_health(catalog_app)

    def test_order_health(self):
        self._assert_health(order_app)

    def test_payment_health(self):
        self._assert_health(payment_app)


if __name__ == "__main__":
    unittest.main()
