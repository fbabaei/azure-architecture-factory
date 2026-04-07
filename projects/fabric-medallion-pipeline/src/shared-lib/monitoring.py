"""
Structured logging and Application Insights telemetry integration.
"""
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional


def configure_logging(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    Configures a structured JSON logger for the given service.
    Outputs to stdout (Container Apps captures stdout) and optionally to file.
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter(service_name))
        logger.addHandler(handler)

    return logger


class _JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def emit_pipeline_event(
    stage: str,
    event_type: str,
    records_processed: int,
    duration_seconds: float,
    extra: Optional[Dict[str, Any]] = None,
    log_path: str = "logs/events.jsonl",
) -> None:
    """Writes a structured pipeline event to the JSONL event log."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "stage": stage,
        "event_type": event_type,
        "records_processed": records_processed,
        "duration_seconds": round(duration_seconds, 3),
        **(extra or {}),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
