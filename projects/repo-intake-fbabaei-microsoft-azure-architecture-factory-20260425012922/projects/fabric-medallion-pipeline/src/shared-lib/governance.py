"""
Governance helpers: field masking and audit lineage emission.
"""
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

from .models import LineageRecord

logger = logging.getLogger(__name__)


def mask_customer_id(customer_id: str) -> str:
    """Replaces customer ID with a consistent, non-reversible masked token."""
    if not customer_id:
        return "CUST_UNKNOWN"
    suffix = customer_id[-4:] if len(customer_id) >= 4 else customer_id
    return f"CUST_****{suffix}"


def mask_amount(amount: float, precision: int = 2) -> float:
    """Rounds amount to reduce precision; keeps financial magnitude intact."""
    return round(amount, precision)


def emit_lineage(record: LineageRecord, log_path: str = "logs/events.jsonl") -> None:
    """Appends a lineage audit record to the structured log file."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "lineage", **record.to_dict()}) + "\n")
    logger.info(
        "Lineage emitted: stage=%s records_in=%d records_out=%d status=%s",
        record.stage, record.records_in, record.records_out, record.status
    )


def apply_field_governance(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies governance rules to a raw record before writing to Silver layer:
    - Masks customer_id
    - Rounds amount
    - Removes any PII fields not in the approved schema
    """
    approved_fields = {"event_id", "event_type", "amount", "timestamp", "source"}
    governed = {k: v for k, v in raw.items() if k in approved_fields}
    governed["customer_id_masked"] = mask_customer_id(raw.get("customer_id", ""))
    if "amount" in governed:
        governed["amount"] = mask_amount(float(governed["amount"]))
    return governed


def compute_record_hash(record: Dict[str, Any]) -> str:
    """Deterministic hash for deduplication (event_id + timestamp)."""
    key = f"{record.get('event_id', '')}:{record.get('timestamp', '')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
