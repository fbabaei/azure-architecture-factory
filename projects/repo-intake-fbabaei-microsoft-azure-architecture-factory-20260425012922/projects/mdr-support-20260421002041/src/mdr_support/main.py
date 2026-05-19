"""FastAPI entrypoint for a document-extraction + clarification workload."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .models import (
    ChatRequest,
    ChatResponse,
    ClarificationBundle,
    DraftResponse,
    ExtractionDraft,
    UploadResponse,
)
from .services.clarification_service import compute_missing_fields
from .services.document_ingestion import ingest_document
from .services.extraction_service import extract_structured_data
from .services.repository import DraftRepository
from .services.session_service import SessionService


logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx", ".md"}

app = FastAPI(title="Generated Extraction + Chat API", version="0.1.0")
_repo = DraftRepository()
_sessions = SessionService()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), notes: str = Form(default="")) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if suffix and suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=415, detail="unsupported file type")
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    ingested = ingest_document(file.filename, payload, notes=notes)
    extraction = extract_structured_data(ingested)
    document_id = str(uuid.uuid4())
    draft = ExtractionDraft(
        document_id=document_id,
        source_filename=file.filename,
        fields=extraction.fields,
        raw_excerpt=extraction.raw_excerpt,
    )
    _repo.put(draft)
    clarifications = compute_missing_fields(draft)
    logger.info("uploaded %s (%s bytes) -> %s", file.filename, len(payload), document_id)
    return UploadResponse(document_id=document_id, clarifications=clarifications, draft=draft)


@app.post("/documents/{document_id}/chat", response_model=ChatResponse)
def chat(document_id: str, payload: ChatRequest) -> ChatResponse:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    if payload.field:
        draft.fields[payload.field] = payload.answer
        _repo.put(draft)
    clarifications = compute_missing_fields(draft)
    _sessions.record_turn(document_id, payload.field or "(free-form)", payload.answer)
    return ChatResponse(document_id=document_id, draft=draft, clarifications=clarifications)


@app.get("/documents/{document_id}", response_model=ExtractionDraft)
def get_document(document_id: str) -> ExtractionDraft:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    return draft


@app.get("/documents/{document_id}/clarifications", response_model=ClarificationBundle)
def get_clarifications(document_id: str) -> ClarificationBundle:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    return ClarificationBundle(document_id=document_id, clarifications=compute_missing_fields(draft))


@app.post("/documents/{document_id}/draft", response_model=DraftResponse)
def finalize_draft(document_id: str) -> DraftResponse:
    draft = _repo.get(document_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="document not found")
    open_items = compute_missing_fields(draft)
    if open_items:
        raise HTTPException(status_code=409, detail={"message": "mandatory fields missing", "clarifications": [c.model_dump() for c in open_items]})
    return DraftResponse(document_id=document_id, draft=draft, finalized_at=datetime.now(timezone.utc).isoformat())
