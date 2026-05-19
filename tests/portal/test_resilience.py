"""Tests for Phase 5: blob retry + stuck-run watchdog."""
from __future__ import annotations

import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import blob_sync
import start_factory_portal as portal


UTC = timezone.utc


class BlobRetryTests(unittest.TestCase):
    def test_retries_on_503_then_succeeds(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError(
                    url="x", code=503, msg="busy", hdrs=None, fp=None
                )
            return b"ok"

        with patch.object(blob_sync.time, "sleep", lambda *_: None):
            result = blob_sync._with_retry("test", flaky)
        self.assertEqual(result, b"ok")
        self.assertEqual(len(calls), 3)

    def test_does_not_retry_403(self):
        calls = []

        def forbidden():
            calls.append(1)
            raise urllib.error.HTTPError(
                url="x", code=403, msg="forbidden", hdrs=None, fp=None
            )

        with self.assertRaises(urllib.error.HTTPError):
            blob_sync._with_retry("test", forbidden)
        self.assertEqual(len(calls), 1)

    def test_gives_up_after_max_retries(self):
        calls = []

        def always_503():
            calls.append(1)
            raise urllib.error.HTTPError(
                url="x", code=503, msg="busy", hdrs=None, fp=None
            )

        with patch.object(blob_sync.time, "sleep", lambda *_: None):
            with self.assertRaises(urllib.error.HTTPError):
                blob_sync._with_retry("test", always_503)
        self.assertEqual(len(calls), blob_sync._MAX_RETRIES)

    def test_retries_url_error(self):
        calls = []

        def transient_network():
            calls.append(1)
            if len(calls) < 2:
                raise urllib.error.URLError("temporarily unreachable")
            return b"ok"

        with patch.object(blob_sync.time, "sleep", lambda *_: None):
            result = blob_sync._with_retry("test", transient_network)
        self.assertEqual(result, b"ok")

    def test_non_retryable_type_error_propagates_immediately(self):
        calls = []

        def type_err():
            calls.append(1)
            raise TypeError("nope")

        with self.assertRaises(TypeError):
            blob_sync._with_retry("test", type_err)
        self.assertEqual(len(calls), 1)


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self._saved_runs = dict(portal.RUNS)
        portal.RUNS.clear()

    def tearDown(self):
        portal.RUNS.clear()
        portal.RUNS.update(self._saved_runs)

    def _stamp(self, minutes_ago: int) -> str:
        """Produce a _utcnow_iso()-shaped timestamp N minutes in the past."""
        t = datetime.now(UTC) - timedelta(minutes=minutes_ago)
        return t.replace(tzinfo=None).isoformat() + "Z"

    def test_marks_stuck_running_as_failed(self):
        portal.RUNS["r1"] = {
            "id": "r1",
            "status": "running",
            "startedAt": self._stamp(minutes_ago=portal._PIPELINE_STUCK_MINUTES + 5),
            "createdAt": self._stamp(minutes_ago=portal._PIPELINE_STUCK_MINUTES + 10),
        }
        n = portal._sweep_stuck_runs()
        self.assertEqual(n, 1)
        self.assertEqual(portal.RUNS["r1"]["status"], "failed")
        self.assertEqual(portal.RUNS["r1"]["returnCode"], -2)
        self.assertIn("watchdog", portal.RUNS["r1"]["stderr"].lower())

    def test_leaves_running_below_threshold_alone(self):
        portal.RUNS["r2"] = {
            "id": "r2",
            "status": "running",
            "startedAt": self._stamp(minutes_ago=1),
        }
        n = portal._sweep_stuck_runs()
        self.assertEqual(n, 0)
        self.assertEqual(portal.RUNS["r2"]["status"], "running")

    def test_leaves_completed_alone(self):
        portal.RUNS["r3"] = {
            "id": "r3",
            "status": "completed",
            "startedAt": self._stamp(minutes_ago=999),
        }
        n = portal._sweep_stuck_runs()
        self.assertEqual(n, 0)
        self.assertEqual(portal.RUNS["r3"]["status"], "completed")

    def test_marks_stuck_queued_as_failed(self):
        # A queued run that never got picked up (pool saturated forever) is
        # still a stuck run; the watchdog should clean it up.
        portal.RUNS["r4"] = {
            "id": "r4",
            "status": "queued",
            "createdAt": self._stamp(minutes_ago=portal._PIPELINE_STUCK_MINUTES + 1),
        }
        n = portal._sweep_stuck_runs()
        self.assertEqual(n, 1)
        self.assertEqual(portal.RUNS["r4"]["status"], "failed")

    def test_skips_run_with_unparseable_timestamp(self):
        portal.RUNS["r5"] = {
            "id": "r5", "status": "running", "startedAt": "not-a-timestamp"
        }
        n = portal._sweep_stuck_runs()
        self.assertEqual(n, 0)
        self.assertEqual(portal.RUNS["r5"]["status"], "running")

    def test_parse_iso_z_roundtrip(self):
        stamp = portal._utcnow_iso()
        parsed = portal._parse_iso_z(stamp)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)


if __name__ == "__main__":
    unittest.main()
