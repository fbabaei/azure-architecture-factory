"""FastAPI entrypoint for the MDR arrangement extraction agent.

Endpoints
---------
- ``GET  /health`` — liveness probe used by Container Apps.
- ``POST /arrangements/upload`` — accept a PDF or text file, persist it,
  extract an initial arrangement draft, and return any open clarification
  questions.
- ``POST /arrangements/{id}/chat`` — human-in-the-loop chat: user answers
  clarification questions, the arrangement draft is updated, and the next
  missing field (if any) is returned.
- ``GET  /arrangements/{id}`` — retrieve the current arrangement draft.
- ``GET  /arrangements/{id}/clarifications`` — poll open clarifications.
- ``POST /arrangements/{id}/draft`` — finalize and return the arrangement
  JSON (rejected while mandatory fields remain missing).
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .config import Settings, get_settings
from .models import (
    ChatRequest,
    ChatResponse,
    ClarificationBundle,
    DraftResponse,
    ExtractionResult,
    ApiChatRequest,
    ApiChatResponse,
    MDRArrangement,
    QARequest,
    QAResponse,
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionSnapshot,
    TextDraftRequest,
    UploadResponse,
)
from .services.agent_runtime import AgentRuntime, build_agent_runtime
from .services.clarification_service import build_clarifications
from .services.document_ingestion import (
    DocumentIngestionService,
    build_ingestion_service,
)
from .services.extraction_agent import (
    ExtractionAgent,
    ExtractionError,
    build_extraction_agent,
)
from .services.qa_service import QAService, build_qa_service
from .services.repository import ArrangementRepository, build_repository

logger = logging.getLogger("mdr_agent")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx"}
ALLOWED_UPLOAD_TYPES = {
    "application/msword",
    "application/octet-stream",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = _settings()
    if settings.appinsights_connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor()
            logger.info("Azure Monitor OpenTelemetry configured")
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to initialize Azure Monitor telemetry: %s", exc)
    yield

app = FastAPI(
    title="MDR Arrangement Extraction Agent",
    version="0.1.0",
    description=(
        "Phase 1 extraction agent for EY Tax MDR arrangement creation. "
        "Ingests PDFs and text inputs, extracts structured arrangement data, "
        "and drives a human-in-the-loop clarification chat."
    ),
    lifespan=lifespan,
)


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def _ingestion() -> DocumentIngestionService:
    return build_ingestion_service(_settings())


@lru_cache(maxsize=1)
def _extractor() -> ExtractionAgent:
    return build_extraction_agent(_settings())


@lru_cache(maxsize=1)
def _repo() -> ArrangementRepository:
    return build_repository(_settings())


@lru_cache(maxsize=1)
def _qa() -> QAService:
    return build_qa_service(_settings())


@lru_cache(maxsize=1)
def _runtime() -> AgentRuntime:
    return build_agent_runtime(
        ingestion=_ingestion(),
        extractor=_extractor(),
        repository=_repo(),
        qa_service=_qa(),
    )


def _new_session_id() -> str:
    return str(uuid.uuid4())


def _validate_upload(file: UploadFile, data: bytes) -> None:
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload exceeds 10 MB limit")

    filename = (file.filename or "upload.bin").strip()
    extension = Path(filename).suffix.lower()
    content_type = (file.content_type or "application/octet-stream").lower()

    if extension and extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=415, detail="unsupported file extension")
    if content_type not in ALLOWED_UPLOAD_TYPES and extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=415, detail="unsupported content type")


@app.get("/health")
def health() -> dict:
    settings = _settings()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "azure_enabled": settings.azure_enabled,
    }


@app.post("/arrangements/upload", response_model=ExtractionResult)
async def upload_document(
    file: UploadFile = File(...),
    reference: str | None = Form(default=None),
    arrangement_id: str | None = Form(default=None),
) -> ExtractionResult:
    data = await file.read()
    _validate_upload(file, data)

    arrangement_id = arrangement_id or str(uuid.uuid4())
    try:
        return _runtime().extraction_agent.extract_document(
            arrangement_id=arrangement_id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            reference=reference,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/session", response_model=SessionCreateResponse)
def create_session() -> SessionCreateResponse:
    session_id = _new_session_id()
    return SessionCreateResponse(session_id=session_id)


@app.get("/api/session/{session_id}", response_model=SessionSnapshot)
def get_session(session_id: str) -> SessionSnapshot:
    arrangement = _repo().get(session_id)
    turns = _repo().get_turns(session_id)
    if arrangement is None and not turns:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionSnapshot(session_id=session_id, arrangement=arrangement, turns=turns)


@app.delete("/api/session/{session_id}", response_model=SessionDeleteResponse)
def delete_session(session_id: str) -> SessionDeleteResponse:
    deleted = _repo().delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionDeleteResponse(session_id=session_id, deleted=True)


@app.post("/api/upload", response_model=ExtractionResult)
async def api_upload_document(
    file: UploadFile = File(...),
    reference: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
) -> ExtractionResult:
    return await upload_document(file=file, reference=reference, arrangement_id=session_id)


@app.post("/api/case/from-text", response_model=ExtractionResult)
def create_case_from_text(payload: TextDraftRequest) -> ExtractionResult:
    arrangement_id = payload.session_id or _new_session_id()
    try:
        return _runtime().extraction_agent.extract_text(
            arrangement_id=arrangement_id,
            text=payload.text,
            reference=payload.reference,
        )
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/chat", response_model=ApiChatResponse)
def api_chat(payload: ApiChatRequest) -> ApiChatResponse:
    session_id = payload.session_id or _new_session_id()
    return _runtime().chat_agent.respond(session_id=session_id, message=payload.message)


@app.get("/arrangements/{arrangement_id}", response_model=MDRArrangement)
def get_arrangement(arrangement_id: str) -> MDRArrangement:
    arrangement = _repo().get(arrangement_id)
    if arrangement is None:
        raise HTTPException(status_code=404, detail="arrangement not found")
    return arrangement


@app.get(
    "/arrangements/{arrangement_id}/clarifications",
    response_model=ClarificationBundle,
)
def get_clarifications(arrangement_id: str) -> ClarificationBundle:
    arrangement = _repo().get(arrangement_id)
    if arrangement is None:
        raise HTTPException(status_code=404, detail="arrangement not found")
    bundle = build_clarifications(arrangement)
    return ClarificationBundle.model_validate(
        {**bundle.model_dump(), "arrangement_id": arrangement_id}
    )


@app.post("/arrangements/{arrangement_id}/chat", response_model=ChatResponse)
def post_chat(arrangement_id: str, payload: ChatRequest) -> ChatResponse:
    if payload.arrangement_id != arrangement_id:
        raise HTTPException(
            status_code=400, detail="arrangement_id mismatch between URL and body"
        )
    try:
        return _runtime().extraction_agent.continue_clarification(
            arrangement_id=arrangement_id,
            user_message=payload.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/arrangements/{arrangement_id}/draft", response_model=DraftResponse)
def finalize_draft(arrangement_id: str) -> DraftResponse:
    arrangement = _repo().get(arrangement_id)
    if arrangement is None:
        raise HTTPException(status_code=404, detail="arrangement not found")
    bundle = build_clarifications(arrangement)
    if not bundle.is_complete:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "arrangement still has open clarifications",
                "missing_fields": bundle.missing_fields,
            },
        )
    return DraftResponse(
        arrangement_id=arrangement_id,
        arrangement=arrangement,
        is_complete=True,
        generated_at=datetime.now(timezone.utc),
    )


@app.get("/api/case/{arrangement_id}", response_model=MDRArrangement)
def api_get_case(arrangement_id: str) -> MDRArrangement:
    return get_arrangement(arrangement_id)


@app.put("/api/case/{arrangement_id}", response_model=MDRArrangement)
def api_update_case(arrangement_id: str, payload: MDRArrangement) -> MDRArrangement:
    updated = payload.model_copy(update={"arrangement_id": arrangement_id})
    _repo().save(updated, reason="case_updated")
    return updated


@app.post("/api/case/{arrangement_id}/confirm", response_model=DraftResponse)
def api_confirm_case(arrangement_id: str) -> DraftResponse:
    draft = finalize_draft(arrangement_id)
    _repo().record_event(
        arrangement_id,
        "case_confirmed",
        details={"is_complete": True},
    )
    return draft


@app.post("/qa", response_model=QAResponse)
def mdr_qa(payload: QARequest) -> QAResponse:
    """Open-ended MDR / DAC6 Q&A endpoint.

    Grounded on a short system prompt that keeps the model focused on
    Mandatory Disclosure Rules. A local fallback answers common topics
    (hallmarks, main-benefit test, intermediary obligations, timing)
    when Azure OpenAI is not configured.
    """
    outcome = _qa().answer(payload.question)
    return QAResponse(
        question=outcome.question,
        answer=outcome.answer,
        model=outcome.model,
    )
