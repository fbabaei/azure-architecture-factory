"""Unit tests for the intake rate limiter and BRD schema tightening."""
from __future__ import annotations

import time
import unittest

import start_factory_portal as portal


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_allows_up_to_limit(self):
        lim = portal._SlidingWindowRateLimiter(limit=3, window_seconds=60)
        for _ in range(3):
            allowed, retry = lim.check("alice")
            self.assertTrue(allowed)
            self.assertEqual(retry, 0)

    def test_rejects_over_limit(self):
        lim = portal._SlidingWindowRateLimiter(limit=2, window_seconds=60)
        self.assertTrue(lim.check("bob")[0])
        self.assertTrue(lim.check("bob")[0])
        allowed, retry = lim.check("bob")
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry, 1)

    def test_keys_are_isolated(self):
        lim = portal._SlidingWindowRateLimiter(limit=1, window_seconds=60)
        self.assertTrue(lim.check("alice")[0])
        self.assertFalse(lim.check("alice")[0])
        # Different key: fresh budget
        self.assertTrue(lim.check("bob")[0])

    def test_empty_key_is_always_allowed(self):
        lim = portal._SlidingWindowRateLimiter(limit=1, window_seconds=60)
        self.assertTrue(lim.check("")[0])
        self.assertTrue(lim.check("")[0])

    def test_window_refills(self):
        lim = portal._SlidingWindowRateLimiter(limit=1, window_seconds=1)
        self.assertTrue(lim.check("carol")[0])
        self.assertFalse(lim.check("carol")[0])
        time.sleep(1.1)
        self.assertTrue(lim.check("carol")[0])

    def test_minimum_limit_coerced_to_one(self):
        lim = portal._SlidingWindowRateLimiter(limit=0, window_seconds=60)
        self.assertTrue(lim.check("k")[0])
        self.assertFalse(lim.check("k")[0])


class UtcnowIsoTests(unittest.TestCase):
    def test_format_matches_legacy(self):
        stamp = portal._utcnow_iso()
        self.assertTrue(stamp.endswith("Z"))
        # Legacy format: YYYY-MM-DDTHH:MM:SS(.ffffff)Z — no timezone offset.
        self.assertNotIn("+00:00", stamp)
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_deprecation_free(self):
        # datetime.utcnow() emits DeprecationWarning on 3.13; our helper must not.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            portal._utcnow_iso()


class BrdSchemaBoundsTests(unittest.TestCase):
    def test_defaults_are_sane(self):
        self.assertGreaterEqual(portal.MIN_BRD_CONTENT_CHARS, 1)
        self.assertGreater(portal.MAX_BRD_CONTENT_CHARS, portal.MIN_BRD_CONTENT_CHARS)
        self.assertLessEqual(portal.MAX_BRD_CONTENT_CHARS, portal.MAX_REQUEST_BYTES)
        self.assertGreater(portal.MAX_BRD_FILENAME_LEN, 0)


if __name__ == "__main__":
    unittest.main()
