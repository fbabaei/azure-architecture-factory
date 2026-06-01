"""Tests for Phase 4b: structured JSON logging + deeper readiness probe."""
from __future__ import annotations

import io
import json
import logging
import pathlib
import unittest

import start_factory_portal as portal


class JsonFormatterTests(unittest.TestCase):
    def setUp(self):
        self.fmt = portal._JsonFormatter()

    def _make_record(self, level=logging.INFO, msg="hello", extra=None, exc_info=None):
        rec = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=None,
            exc_info=exc_info,
        )
        if extra:
            for k, v in extra.items():
                setattr(rec, k, v)
        return rec

    def test_emits_valid_json_with_core_fields(self):
        out = self.fmt.format(self._make_record())
        payload = json.loads(out)
        self.assertEqual(payload["msg"], "hello")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "test.logger")
        self.assertTrue(payload["ts"].endswith("Z"))

    def test_extras_merged_as_top_level_keys(self):
        rec = self._make_record(
            extra={"run_id": "abc-123", "owner": "alice@contoso.com"}
        )
        payload = json.loads(self.fmt.format(rec))
        self.assertEqual(payload["run_id"], "abc-123")
        self.assertEqual(payload["owner"], "alice@contoso.com")

    def test_non_json_extras_fall_back_to_repr(self):
        class Weird:
            def __repr__(self): return "<Weird>"
        rec = self._make_record(extra={"obj": Weird()})
        payload = json.loads(self.fmt.format(rec))
        self.assertEqual(payload["obj"], "<Weird>")

    def test_exception_rendered_as_exc_field(self):
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            import sys
            rec = self._make_record(exc_info=sys.exc_info())
        payload = json.loads(self.fmt.format(rec))
        self.assertIn("exc", payload)
        self.assertIn("RuntimeError: boom", payload["exc"])

    def test_stdlib_reserved_attrs_not_leaked(self):
        rec = self._make_record()
        payload = json.loads(self.fmt.format(rec))
        for banned in ("pathname", "lineno", "filename", "processName"):
            self.assertNotIn(banned, payload)

    def test_integrates_with_logger_extra(self):
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(portal._JsonFormatter())
        log = logging.getLogger("aaf.jsonfmt.test")
        log.handlers = [handler]
        log.setLevel(logging.INFO)
        log.propagate = False
        log.info("run started", extra={"run_id": "xyz", "owner": "u@x"})
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload["run_id"], "xyz")
        self.assertEqual(payload["owner"], "u@x")


class IntakeWritableProbeTests(unittest.TestCase):
    def test_returns_true_for_writable_dir(self, tmpdir=None):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(portal._probe_intake_writable(pathlib.Path(td)))

    def test_returns_false_for_unwritable_path(self):
        # A file path (not a dir) can't be mkdir'd — probe should fail gracefully.
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            blocking_path = pathlib.Path(tf.name)
        try:
            child = blocking_path / "cannot-make-subdir"
            self.assertFalse(portal._probe_intake_writable(child))
        finally:
            blocking_path.unlink(missing_ok=True)


class OtelEnabledProbeTests(unittest.TestCase):
    def test_returns_boolean(self):
        self.assertIsInstance(portal._otel_enabled(), bool)


if __name__ == "__main__":
    unittest.main()
