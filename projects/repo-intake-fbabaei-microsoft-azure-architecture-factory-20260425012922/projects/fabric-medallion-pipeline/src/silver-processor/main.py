"""
Silver Processor — Entry point.

Reads Bronze-layer JSONL, applies validation rules, deduplication,
field masking (governance), and writes clean records to the Silver layer.
"""
import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared_lib.config import PipelineConfig
from shared_lib.governance import apply_field_governance, compute_record_hash, emit_lineage
from shared_lib.models import LineageRecord, RawEvent, ValidatedEvent
from shared_lib.monitoring import configure_logging, emit_pipeline_event
from shared_lib.resilience import with_retry

logger = configure_logging("silver-processor")

REQUIRED_FIELDS = {"event_id", "customer_id", "event_type", "amount", "timestamp"}
VALID_EVENT_TYPES = {"purchase", "refund", "subscription", "cancellation", "view", "click"}


def validate_record(raw: dict) -> Tuple[bool, List[str]]:
    """Returns (is_valid, [error_messages])."""
    errors: List[str] = []
    missing = REQUIRED_FIELDS - set(raw.keys())
    if missing:
        errors.append(f"Missing required fields: {missing}")
    if "amount" in raw:
        try:
            val = float(raw["amount"])
            if val < 0:
                errors.append(f"Negative amount: {val}")
        except (TypeError, ValueError):
            errors.append(f"Non-numeric amount: {raw['amount']}")
    if "event_type" in raw and raw["event_type"] not in VALID_EVENT_TYPES:
        errors.append(f"Unknown event_type: {raw['event_type']}")
    return len(errors) == 0, errors


def load_bronze(bronze_path: str) -> List[dict]:
    if not os.path.exists(bronze_path):
        logger.warning("Bronze file not found: %s", bronze_path)
        return []
    records = []
    with open(bronze_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def process_records(raw_records: List[dict]) -> Tuple[List[ValidatedEvent], int, int]:
    valid_events: List[ValidatedEvent] = []
    seen_hashes: Set[str] = set()
    failed = 0

    for raw in raw_records:
        record_hash = compute_record_hash(raw)
        if record_hash in seen_hashes:
            logger.debug("Duplicate skipped: event_id=%s", raw.get("event_id"))
            continue
        seen_hashes.add(record_hash)

        is_valid, errors = validate_record(raw)
        governed = apply_field_governance(raw) if is_valid else {}

        try:
            ts = datetime.fromisoformat(raw.get("timestamp", "")) if "timestamp" in raw else datetime.utcnow()
        except ValueError:
            ts = datetime.utcnow()

        event = ValidatedEvent(
            event_id=raw.get("event_id", ""),
            customer_id_masked=governed.get("customer_id_masked", "CUST_UNKNOWN"),
            event_type=raw.get("event_type", ""),
            amount=float(governed.get("amount", 0)),
            timestamp=ts,
            is_valid=is_valid,
            validation_errors=errors,
            lineage_source=raw.get("source", "unknown"),
        )
        if is_valid:
            valid_events.append(event)
        else:
            failed += 1
            logger.warning("Invalid record event_id=%s errors=%s", event.event_id, errors)

    return valid_events, len(raw_records), failed


def write_silver(events: List[ValidatedEvent], output_path: str) -> int:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e.to_dict()) + "\n")
    logger.info("Wrote %d validated records to Silver: %s", len(events), output_path)
    return len(events)


def run(config: PipelineConfig) -> dict:
    run_id = str(uuid.uuid4())[:8]
    started_at = datetime.utcnow().isoformat()
    t0 = time.monotonic()

    bronze_path = os.path.join("outputs", config.storage.bronze_path, "bronze.jsonl")
    silver_path = os.path.join("outputs", config.storage.silver_path, "silver.jsonl")

    raw_records = load_bronze(bronze_path)
    valid_events, total_in, failed = process_records(raw_records)
    records_out = write_silver(valid_events, silver_path)

    elapsed = time.monotonic() - t0
    completed_at = datetime.utcnow().isoformat()
    status = "success" if failed == 0 else "partial"

    emit_lineage(
        LineageRecord(
            pipeline_run_id=run_id,
            stage="silver",
            records_in=total_in,
            records_out=records_out,
            records_failed=failed,
            source_path=bronze_path,
            destination_path=silver_path,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
        )
    )
    emit_pipeline_event(
        stage="silver",
        event_type="validation_complete",
        records_processed=records_out,
        duration_seconds=elapsed,
        extra={"records_failed": failed, "status": status},
    )

    return {"run_id": run_id, "records_in": total_in, "records_out": records_out, "failed": failed, "status": status}


def main() -> None:
    parser = argparse.ArgumentParser(description="Silver Processor Service")
    parser.add_argument("--mode", choices=["live", "sample"], default="sample")
    args = parser.parse_args()

    os.environ.setdefault("PIPELINE_MODE", args.mode)
    os.environ.setdefault("ADLS_ACCOUNT_NAME", "devstorageaccount")
    os.environ.setdefault("ADLS_CONTAINER", "medallion")

    config = PipelineConfig.from_env()
    result = run(config)
    logger.info("Silver processing complete: %s", result)


if __name__ == "__main__":
    main()
