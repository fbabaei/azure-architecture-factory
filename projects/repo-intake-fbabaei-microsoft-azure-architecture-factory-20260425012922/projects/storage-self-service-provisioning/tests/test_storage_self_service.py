from __future__ import annotations

import os
import sys
import tempfile
import unittest
import importlib
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


class StorageSelfServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "requests.json"
        os.environ["REQUEST_DATA_FILE"] = str(self.data_file)
        os.environ["REQUEST_REPOSITORY_BACKEND"] = "local"
        os.environ["STORAGE_PROVISIONER_BACKEND"] = "local"
        os.environ["EVENT_PUBLISHER_BACKEND"] = "log"

        api_main = importlib.import_module("provisioning_api.main")

        api_main.settings = api_main.Settings.from_env(PROJECT_ROOT)
        api_main.repository = api_main.create_request_repository(api_main.settings)
        api_main.event_publisher = api_main.create_event_publisher(api_main.settings)
        self.client = TestClient(api_main.app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_request_lifecycle(self) -> None:
        create_response = self.client.post(
            "/requests",
            json={
                "project": "lakehouse",
                "team": "ops-team",
                "environment": "dev",
                "data_class": "internal",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        request_id = create_response.json()["request_id"]

        process_pending_requests = importlib.import_module(
            "workflow_worker.main"
        ).process_pending_requests

        processed = process_pending_requests()
        self.assertEqual(processed, 1)

        get_response = self.client.get(f"/requests/{request_id}")
        self.assertEqual(get_response.status_code, 200)
        body = get_response.json()
        self.assertEqual(body["status"], "COMPLETED")
        self.assertIn("storage_account", body["resources"])
        self.assertIn("adls_container", body["resources"])


if __name__ == "__main__":
    unittest.main()
