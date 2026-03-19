"""
Test suite for the Fabric Medallion Pipeline — covers all three stages.
Run: python -m pytest tests/ -v
  or: python -m unittest discover tests/
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Allow importing from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared_lib.config import PipelineConfig, ResilienceConfig, StorageConfig
from shared_lib.governance import (
    apply_field_governance,
    compute_record_hash,
    mask_customer_id,
    mask_amount,
)
from shared_lib.models import (
    CustomerMetric,
    EventTypeMetric,
    LineageRecord,
    RawEvent,
    ValidatedEvent,
)
from shared_lib.resilience import CircuitBreakerOpen, with_retry


# ─────────────────────────────────────────────────────────────
# Governance Tests
# ─────────────────────────────────────────────────────────────

class TestGovernanceMasking(unittest.TestCase):

    def test_mask_customer_id_standard(self):
        masked = mask_customer_id("CUSTOMER_12345")
        self.assertTrue(masked.startswith("CUST_****"))
        self.assertNotIn("CUSTOMER_12345", masked)

    def test_mask_customer_id_short(self):
        masked = mask_customer_id("AB")
        self.assertIn("CUST_", masked)

    def test_mask_customer_id_empty(self):
        masked = mask_customer_id("")
        self.assertEqual(masked, "CUST_UNKNOWN")

    def test_mask_amount_precision(self):
        self.assertEqual(mask_amount(123.456789, 2), 123.46)
        self.assertEqual(mask_amount(0.0), 0.0)

    def test_apply_field_governance_removes_pii(self):
        raw = {
            "event_id": "E001",
            "customer_id": "CUST_SECRET_999",
            "event_type": "purchase",
            "amount": 99.99,
            "timestamp": "2026-03-19T00:00:00",
            "source": "adls",
            "internal_field": "should_be_removed",
        }
        governed = apply_field_governance(raw)
        self.assertNotIn("customer_id", governed)
        self.assertNotIn("internal_field", governed)
        self.assertIn("customer_id_masked", governed)
        self.assertEqual(governed["event_id"], "E001")

    def test_compute_record_hash_deterministic(self):
        rec = {"event_id": "E001", "timestamp": "2026-03-19T00:00:00"}
        h1 = compute_record_hash(rec)
        h2 = compute_record_hash(rec)
        self.assertEqual(h1, h2)

    def test_compute_record_hash_different_inputs(self):
        h1 = compute_record_hash({"event_id": "E001", "timestamp": "T1"})
        h2 = compute_record_hash({"event_id": "E002", "timestamp": "T1"})
        self.assertNotEqual(h1, h2)


# ─────────────────────────────────────────────────────────────
# Resilience Tests
# ─────────────────────────────────────────────────────────────

class TestResilienceRetry(unittest.TestCase):

    def test_retry_succeeds_on_first_attempt(self):
        call_count = {"n": 0}

        @with_retry(max_retries=3, base_delay=0)
        def always_succeeds():
            call_count["n"] += 1
            return "ok"

        result = always_succeeds()
        self.assertEqual(result, "ok")
        self.assertEqual(call_count["n"], 1)

    def test_retry_eventually_succeeds(self):
        call_count = {"n": 0}

        @with_retry(max_retries=3, base_delay=0)
        def fails_twice():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise ValueError("transient error")
            return "success"

        result = fails_twice()
        self.assertEqual(result, "success")
        self.assertEqual(call_count["n"], 3)

    def test_retry_raises_after_max_retries(self):
        call_count = {"n": 0}

        @with_retry(max_retries=2, base_delay=0)
        def always_fails():
            call_count["n"] += 1
            raise ConnectionError("permanent error")

        with self.assertRaises(ConnectionError):
            always_fails()
        self.assertEqual(call_count["n"], 3)  # 1 initial + 2 retries


# ─────────────────────────────────────────────────────────────
# Bronze Stage Tests
# ─────────────────────────────────────────────────────────────

class TestBronzeIngestion(unittest.TestCase):

    def setUp(self):
        self.config = PipelineConfig(
            environment="dev",
            azure_region="eastus",
            storage=StorageConfig(account_name="test", container_name="medallion"),
            mode="sample",
        )

    def test_raw_event_roundtrip(self):
        raw = {
            "event_id": "E001",
            "customer_id": "C001",
            "event_type": "purchase",
            "amount": "49.99",
            "timestamp": "2026-03-19T00:00:00",
            "source": "adls",
        }
        event = RawEvent.from_dict(raw)
        self.assertEqual(event.event_id, "E001")
        self.assertEqual(event.amount, 49.99)
        exported = event.to_dict()
        self.assertEqual(exported["event_type"], "purchase")

    def test_bronze_writes_to_output(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "bronze-ingestion"))
        import main as bronze

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "bronze", "bronze.jsonl")
            events = [
                RawEvent("E1", "C1", "purchase", 10.0, "2026-03-19T00:00:00", "adls"),
                RawEvent("E2", "C2", "refund", 5.0, "2026-03-19T00:01:00", "snowflake"),
            ]
            count = bronze.write_bronze(events, output)
            self.assertEqual(count, 2)
            self.assertTrue(os.path.exists(output))
            with open(output) as f:
                lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(lines), 2)


# ─────────────────────────────────────────────────────────────
# Silver Stage Tests
# ─────────────────────────────────────────────────────────────

class TestSilverProcessor(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "silver-processor"))
        import main as silver
        self.silver = silver

    def test_valid_record_passes_validation(self):
        raw = {
            "event_id": "E001",
            "customer_id": "CUST_001",
            "event_type": "purchase",
            "amount": 49.99,
            "timestamp": "2026-03-19T00:00:00",
        }
        is_valid, errors = self.silver.validate_record(raw)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_missing_required_field_fails_validation(self):
        raw = {"event_id": "E001", "event_type": "purchase", "amount": 10.0, "timestamp": "2026-03-19T00:00:00"}
        is_valid, errors = self.silver.validate_record(raw)
        self.assertFalse(is_valid)
        self.assertTrue(any("customer_id" in str(e) for e in errors))

    def test_negative_amount_fails_validation(self):
        raw = {
            "event_id": "E001", "customer_id": "C001", "event_type": "purchase",
            "amount": -1.0, "timestamp": "2026-01-01T00:00:00",
        }
        is_valid, errors = self.silver.validate_record(raw)
        self.assertFalse(is_valid)

    def test_deduplication_removes_duplicates(self):
        rec = {
            "event_id": "E001", "customer_id": "C001", "event_type": "purchase",
            "amount": 10.0, "timestamp": "2026-03-19T00:00:00",
        }
        valid_events, total, failed = self.silver.process_records([rec, rec])
        # Duplicate should be dropped: len(valid_events) == 1
        self.assertEqual(len(valid_events), 1)


# ─────────────────────────────────────────────────────────────
# Gold Stage Tests
# ─────────────────────────────────────────────────────────────

class TestGoldAggregator(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "gold-aggregator"))
        import main as gold
        self.gold = gold

    def _make_silver_records(self):
        return [
            {"event_id": "E1", "customer_id_masked": "CUST_****001", "event_type": "purchase", "amount": 100.0, "is_valid": True},
            {"event_id": "E2", "customer_id_masked": "CUST_****001", "event_type": "refund",   "amount": 20.0,  "is_valid": True},
            {"event_id": "E3", "customer_id_masked": "CUST_****002", "event_type": "purchase", "amount": 50.0,  "is_valid": True},
            {"event_id": "E4", "customer_id_masked": "CUST_****002", "event_type": "purchase", "amount": 30.0,  "is_valid": True},
        ]

    def test_customer_aggregation(self):
        records = self._make_silver_records()
        metrics = self.gold.aggregate_customers(records)
        c001 = next((m for m in metrics if m.customer_id_masked == "CUST_****001"), None)
        self.assertIsNotNone(c001)
        self.assertAlmostEqual(c001.total_amount, 120.0)
        self.assertEqual(c001.event_count, 2)

    def test_event_type_aggregation(self):
        records = self._make_silver_records()
        metrics = self.gold.aggregate_event_types(records)
        purchases = next((m for m in metrics if m.event_type == "purchase"), None)
        self.assertIsNotNone(purchases)
        self.assertEqual(purchases.count, 3)
        self.assertAlmostEqual(purchases.total_amount, 180.0)

    def test_gold_output_sorted_by_total(self):
        records = self._make_silver_records()
        metrics = self.gold.aggregate_customers(records)
        totals = [m.total_amount for m in metrics]
        self.assertEqual(totals, sorted(totals, reverse=True))


# ─────────────────────────────────────────────────────────────
# Model Tests
# ─────────────────────────────────────────────────────────────

class TestLineageModel(unittest.TestCase):

    def test_lineage_record_serializable(self):
        rec = LineageRecord(
            pipeline_run_id="run-001",
            stage="bronze",
            records_in=100,
            records_out=100,
            records_failed=0,
            source_path="adls://incoming",
            destination_path="outputs/bronze/bronze.jsonl",
            started_at="2026-03-19T00:00:00",
            completed_at="2026-03-19T00:01:00",
            status="success",
        )
        d = rec.to_dict()
        self.assertEqual(d["stage"], "bronze")
        self.assertEqual(d["records_in"], 100)
        serialized = json.dumps(d)
        self.assertIn("success", serialized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
