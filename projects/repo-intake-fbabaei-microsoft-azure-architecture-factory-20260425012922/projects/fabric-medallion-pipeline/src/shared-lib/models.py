"""
Shared event models for the Fabric Medallion Pipeline.
Defines raw, validated, and aggregated record schemas.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RawEvent:
    """Bronze-layer raw event record — schema matches ADLS/Snowflake source."""
    event_id: str
    customer_id: str
    event_type: str
    amount: float
    timestamp: str
    source: str  # "adls" | "snowflake"
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "customer_id": self.customer_id,
            "event_type": self.event_type,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "source": self.source,
            "raw_payload": self.raw_payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawEvent":
        return cls(
            event_id=data["event_id"],
            customer_id=data["customer_id"],
            event_type=data["event_type"],
            amount=float(data.get("amount", 0)),
            timestamp=data["timestamp"],
            source=data.get("source", "unknown"),
            raw_payload=data,
        )


@dataclass
class ValidatedEvent:
    """Silver-layer validated event — masked, deduplicated, cleaned."""
    event_id: str
    customer_id_masked: str   # e.g. "CUST_****1234"
    event_type: str
    amount: float
    timestamp: datetime
    is_valid: bool
    validation_errors: List[str] = field(default_factory=list)
    lineage_source: str = ""
    processed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "customer_id_masked": self.customer_id_masked,
            "event_type": self.event_type,
            "amount": self.amount,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "lineage_source": self.lineage_source,
            "processed_at": self.processed_at,
        }


@dataclass
class CustomerMetric:
    """Gold-layer customer-level aggregate."""
    customer_id_masked: str
    total_amount: float
    event_count: int
    avg_amount: float
    event_types: List[str] = field(default_factory=list)
    period_start: str = ""
    period_end: str = ""
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id_masked": self.customer_id_masked,
            "total_amount": round(self.total_amount, 2),
            "event_count": self.event_count,
            "avg_amount": round(self.avg_amount, 2),
            "event_types": self.event_types,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "computed_at": self.computed_at,
        }


@dataclass
class EventTypeMetric:
    """Gold-layer event-type aggregate."""
    event_type: str
    total_amount: float
    count: int
    avg_amount: float
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "total_amount": round(self.total_amount, 2),
            "count": self.count,
            "avg_amount": round(self.avg_amount, 2),
            "computed_at": self.computed_at,
        }


@dataclass
class LineageRecord:
    """Audit trail entry for data lineage tracking."""
    pipeline_run_id: str
    stage: str           # "bronze" | "silver" | "gold"
    records_in: int
    records_out: int
    records_failed: int
    source_path: str
    destination_path: str
    started_at: str
    completed_at: str
    status: str          # "success" | "partial" | "failed"

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__
