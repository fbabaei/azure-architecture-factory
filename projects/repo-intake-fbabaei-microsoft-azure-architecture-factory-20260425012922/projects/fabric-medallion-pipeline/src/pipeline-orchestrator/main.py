"""
Pipeline Orchestrator — runs all three medallion stages in sequence.

Usage:
    python main.py --mode sample
    python main.py --mode live
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

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import each stage runner
import importlib.util

def _load_stage(service_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(
        service_name,
        Path(__file__).parent.parent / rel_path / "main.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


from shared_lib.config import PipelineConfig
from shared_lib.monitoring import configure_logging, emit_pipeline_event

logger = configure_logging("pipeline-orchestrator")


def run_pipeline(config: PipelineConfig) -> dict:
    run_id = str(uuid.uuid4())[:8]
    pipeline_start = time.monotonic()
    results = {}

    stages = [
        ("bronze", "bronze-ingestion"),
        ("silver", "silver-processor"),
        ("gold", "gold-aggregator"),
    ]

    for stage_name, service_dir in stages:
        logger.info("Starting stage: %s", stage_name)
        t0 = time.monotonic()
        try:
            stage_mod = _load_stage(stage_name, service_dir)
            result = stage_mod.run(config)
            elapsed = time.monotonic() - t0
            logger.info("Stage %s complete in %.2fs: %s", stage_name, elapsed, result)
            results[stage_name] = {**result, "duration_seconds": round(elapsed, 3)}
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("Stage %s failed after %.2fs: %s", stage_name, elapsed, exc)
            results[stage_name] = {"status": "failed", "error": str(exc), "duration_seconds": round(elapsed, 3)}
            break  # Stop pipeline on first failure (fail-fast)

    total_elapsed = time.monotonic() - pipeline_start
    overall_status = "success" if all(r.get("status") == "success" for r in results.values()) else "partial"

    emit_pipeline_event(
        stage="pipeline",
        event_type="run_complete",
        records_processed=sum(r.get("records", r.get("records_out", 0)) for r in results.values()),
        duration_seconds=total_elapsed,
        extra={"run_id": run_id, "status": overall_status, "stages": list(results.keys())},
    )

    return {
        "run_id": run_id,
        "status": overall_status,
        "total_duration_seconds": round(total_elapsed, 3),
        "stages": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fabric Medallion Pipeline Orchestrator")
    parser.add_argument("--mode", choices=["live", "sample"], default="sample")
    args = parser.parse_args()

    os.environ.setdefault("PIPELINE_MODE", args.mode)
    os.environ.setdefault("ADLS_ACCOUNT_NAME", "devstorageaccount")
    os.environ.setdefault("ADLS_CONTAINER", "medallion")

    config = PipelineConfig.from_env()
    config.mode = args.mode
    result = run_pipeline(config)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
