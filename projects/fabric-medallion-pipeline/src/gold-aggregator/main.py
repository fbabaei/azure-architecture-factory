"""
Gold Aggregator — Entry point.

Reads Silver-layer validated events and produces two Gold aggregates:
  1. customer_metrics.jsonl   — per-customer totals
  2. event_type_metrics.jsonl — per-event-type totals
"""
import argparse
import json
import logging
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared_lib.config import PipelineConfig
from shared_lib.governance import emit_lineage
from shared_lib.models import CustomerMetric, EventTypeMetric, LineageRecord, ValidatedEvent
from shared_lib.monitoring import configure_logging, emit_pipeline_event
from shared_lib.resilience import with_retry

logger = configure_logging("gold-aggregator")


def load_silver(silver_path: str) -> List[dict]:
    if not os.path.exists(silver_path):
        logger.warning("Silver file not found: %s", silver_path)
        return []
    records = []
    with open(silver_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def aggregate_customers(records: List[dict]) -> List[CustomerMetric]:
    buckets: Dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0, "types": set()})
    for r in records:
        if not r.get("is_valid", True):
            continue
        cid = r.get("customer_id_masked", "UNKNOWN")
        buckets[cid]["total"] += float(r.get("amount", 0))
        buckets[cid]["count"] += 1
        buckets[cid]["types"].add(r.get("event_type", ""))

    metrics = []
    for cid, data in buckets.items():
        avg = data["total"] / data["count"] if data["count"] > 0 else 0.0
        metrics.append(CustomerMetric(
            customer_id_masked=cid,
            total_amount=round(data["total"], 2),
            event_count=data["count"],
            avg_amount=round(avg, 2),
            event_types=sorted(data["types"]),
            computed_at=datetime.utcnow().isoformat(),
        ))
    return sorted(metrics, key=lambda m: m.total_amount, reverse=True)


def aggregate_event_types(records: List[dict]) -> List[EventTypeMetric]:
    buckets: Dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0})
    for r in records:
        if not r.get("is_valid", True):
            continue
        etype = r.get("event_type", "unknown")
        buckets[etype]["total"] += float(r.get("amount", 0))
        buckets[etype]["count"] += 1

    metrics = []
    for etype, data in buckets.items():
        avg = data["total"] / data["count"] if data["count"] > 0 else 0.0
        metrics.append(EventTypeMetric(
            event_type=etype,
            total_amount=round(data["total"], 2),
            count=data["count"],
            avg_amount=round(avg, 2),
        ))
    return sorted(metrics, key=lambda m: m.count, reverse=True)


def write_gold(metrics: list, output_path: str) -> int:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for m in metrics:
            f.write(json.dumps(m.to_dict()) + "\n")
    logger.info("Wrote %d records to Gold: %s", len(metrics), output_path)
    return len(metrics)


def run(config: PipelineConfig) -> dict:
    run_id = str(uuid.uuid4())[:8]
    started_at = datetime.utcnow().isoformat()
    t0 = time.monotonic()

    silver_path = os.path.join("outputs", config.storage.silver_path, "silver.jsonl")
    gold_customer_path = os.path.join("outputs", config.storage.gold_path, "customer_metrics.jsonl")
    gold_event_path = os.path.join("outputs", config.storage.gold_path, "event_type_metrics.jsonl")

    records = load_silver(silver_path)
    customer_metrics = aggregate_customers(records)
    event_type_metrics = aggregate_event_types(records)

    c_count = write_gold(customer_metrics, gold_customer_path)
    e_count = write_gold(event_type_metrics, gold_event_path)
    total_out = c_count + e_count

    elapsed = time.monotonic() - t0
    completed_at = datetime.utcnow().isoformat()

    emit_lineage(
        LineageRecord(
            pipeline_run_id=run_id,
            stage="gold",
            records_in=len(records),
            records_out=total_out,
            records_failed=0,
            source_path=silver_path,
            destination_path=f"{gold_customer_path}, {gold_event_path}",
            started_at=started_at,
            completed_at=completed_at,
            status="success",
        )
    )
    emit_pipeline_event(
        stage="gold",
        event_type="aggregation_complete",
        records_processed=total_out,
        duration_seconds=elapsed,
        extra={"customer_metrics": c_count, "event_type_metrics": e_count},
    )

    return {
        "run_id": run_id,
        "records_in": len(records),
        "customer_metrics": c_count,
        "event_type_metrics": e_count,
        "status": "success",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gold Aggregator Service")
    parser.add_argument("--mode", choices=["live", "sample"], default="sample")
    args = parser.parse_args()

    os.environ.setdefault("PIPELINE_MODE", args.mode)
    os.environ.setdefault("ADLS_ACCOUNT_NAME", "devstorageaccount")
    os.environ.setdefault("ADLS_CONTAINER", "medallion")

    config = PipelineConfig.from_env()
    result = run(config)
    logger.info("Gold aggregation complete: %s", result)


if __name__ == "__main__":
    main()
