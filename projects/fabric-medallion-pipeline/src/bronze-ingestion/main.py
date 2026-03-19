"""
Bronze Ingestion Service — Entry point.

Reads raw events from ADLS Gen2 and/or Snowflake Mirror, applies resilience
policies, and writes them to the Bronze layer (ADLS Gen2 bronze/ partition).

Usage:
    python main.py --mode sample      # uses bundled sample data
    python main.py --mode live        # connects to real Azure services
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
from typing import Iterator, List

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared_lib.config import PipelineConfig
from shared_lib.governance import emit_lineage
from shared_lib.models import LineageRecord, RawEvent
from shared_lib.monitoring import configure_logging, emit_pipeline_event
from shared_lib.resilience import with_retry

logger = configure_logging("bronze-ingestion")


def load_sample_adls_events(sample_dir: str = "sample_data") -> List[RawEvent]:
    sample_path = Path(__file__).parent / sample_dir / "adls_events.jsonl"
    if not sample_path.exists():
        logger.warning("Sample file not found: %s", sample_path)
        return []
    events = []
    with open(sample_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(RawEvent.from_dict(json.loads(line)))
    return events


def load_sample_snowflake_events(sample_dir: str = "sample_data") -> List[RawEvent]:
    sample_path = Path(__file__).parent / sample_dir / "snowflake_mirror.jsonl"
    if not sample_path.exists():
        logger.warning("Sample file not found: %s", sample_path)
        return []
    events = []
    with open(sample_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                data["source"] = "snowflake"
                events.append(RawEvent.from_dict(data))
    return events


@with_retry(max_retries=3, base_delay=1.0, circuit_name="adls-read")
def fetch_adls_events(config: PipelineConfig) -> List[RawEvent]:
    """Connects to ADLS Gen2 and reads raw event files from the source container."""
    from azure.identity import ManagedIdentityCredential
    from azure.storage.filedatalake import DataLakeServiceClient

    credential = ManagedIdentityCredential()
    service = DataLakeServiceClient(
        account_url=f"https://{config.storage.account_name}.dfs.core.windows.net",
        credential=credential,
    )
    fs = service.get_file_system_client(config.storage.container_name)
    events: List[RawEvent] = []
    for item in fs.get_paths("incoming"):
        if item.name.endswith(".jsonl"):
            file_client = fs.get_file_client(item.name)
            content = file_client.download_file().readall().decode("utf-8")
            for line in content.splitlines():
                if line.strip():
                    events.append(RawEvent.from_dict(json.loads(line)))
    return events


def write_bronze(events: List[RawEvent], output_path: str) -> int:
    """Writes raw events to the Bronze JSONL output (local or ADLS)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    written = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event.to_dict()) + "\n")
            written += 1
    logger.info("Wrote %d records to Bronze: %s", written, output_path)
    return written


def run(config: PipelineConfig) -> dict:
    run_id = str(uuid.uuid4())[:8]
    started_at = datetime.utcnow().isoformat()
    t0 = time.monotonic()

    if config.mode == "sample":
        adls_events = load_sample_adls_events()
        snowflake_events = load_sample_snowflake_events()
    else:
        adls_events = fetch_adls_events(config)
        snowflake_events = []  # extend with live Snowflake connector in V2

    all_events = adls_events + snowflake_events
    output_path = os.path.join("outputs", config.storage.bronze_path, "bronze.jsonl")
    records_written = write_bronze(all_events, output_path)

    elapsed = time.monotonic() - t0
    completed_at = datetime.utcnow().isoformat()

    emit_lineage(
        LineageRecord(
            pipeline_run_id=run_id,
            stage="bronze",
            records_in=len(all_events),
            records_out=records_written,
            records_failed=0,
            source_path="adls://incoming + snowflake://mirror",
            destination_path=output_path,
            started_at=started_at,
            completed_at=completed_at,
            status="success",
        )
    )
    emit_pipeline_event(
        stage="bronze",
        event_type="ingestion_complete",
        records_processed=records_written,
        duration_seconds=elapsed,
    )

    return {"run_id": run_id, "records": records_written, "status": "success", "output": output_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bronze Ingestion Service")
    parser.add_argument("--mode", choices=["live", "sample"], default="sample")
    args = parser.parse_args()

    os.environ.setdefault("PIPELINE_MODE", args.mode)
    os.environ.setdefault("ADLS_ACCOUNT_NAME", "devstorageaccount")
    os.environ.setdefault("ADLS_CONTAINER", "medallion")

    config = PipelineConfig.from_env()
    config.mode = args.mode
    result = run(config)
    logger.info("Bronze ingestion complete: %s", result)


if __name__ == "__main__":
    main()
