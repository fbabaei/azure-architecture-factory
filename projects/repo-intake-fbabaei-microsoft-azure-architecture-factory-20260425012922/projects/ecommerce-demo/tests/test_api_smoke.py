import unittest
from pathlib import Path
import sys

PROJECT_WEB = Path(__file__).resolve().parents[1] / "web"
sys.path.insert(0, str(PROJECT_WEB))

from app import app  # noqa: E402


class EcommerceApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_products_endpoint(self):
        response = self.client.get("/api/products")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload, list)
        self.assertGreater(len(payload), 0)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "healthy")


if __name__ == "__main__":
    unittest.main()
