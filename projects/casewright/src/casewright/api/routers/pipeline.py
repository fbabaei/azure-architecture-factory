from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from casewright.core.models import IndexerStatus
from casewright.ingestion.pipeline import IngestionPipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@lru_cache
def _get_pipeline() -> IngestionPipeline:
    return IngestionPipeline()


@router.post("/setup-pipeline")
async def setup_pipeline() -> dict[str, str]:
    """Idempotently create/update data source, index, skillsets, and indexers."""
    await _get_pipeline().setup()
    return {"status": "configured"}


@router.post("/run-indexer")
async def run_indexer(indexer_name: str = "casewright-multimodal-indexer") -> dict[str, str]:
    await _get_pipeline().run_indexer(indexer_name)
    return {"status": "started", "indexer": indexer_name}


@router.get("/indexer-status", response_model=IndexerStatus)
async def indexer_status(
    indexer_name: str = "casewright-multimodal-indexer",
) -> IndexerStatus:
    status = await _get_pipeline().get_indexer_status(indexer_name)
    if status is None:
        raise HTTPException(status_code=404, detail=f"indexer {indexer_name} not found")
    return status
