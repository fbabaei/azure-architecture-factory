"""Logical two-agent runtime for the MDR support application.

This keeps the current FastAPI host while making the chat/extraction split
explicit in code: a Chat Orchestrator Agent decides which capability to invoke,
and an Extraction Specialist Agent owns document/text extraction plus
clarification-driven case refinement.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import ApiChatResponse, ExtractionResult
from .chat_session import handle_chat_turn
from .document_ingestion import DocumentIngestionService
from .extraction_agent import ExtractionAgent
from .guardrails import is_off_topic, off_topic_reply
from .qa_service import QAService
from .repository import ArrangementRepository


@dataclass(frozen=True)
class ExtractionSpecialistAgent:
    ingestion: DocumentIngestionService
    extractor: ExtractionAgent
    repository: ArrangementRepository

    def extract_document(
        self,
        *,
        arrangement_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        reference: str | None = None,
    ) -> ExtractionResult:
        ingested = self.ingestion.ingest(
            arrangement_id=arrangement_id,
            filename=filename,
            content_type=content_type,
            data=data,
        )
        outcome = self.extractor.extract(ingested.text)
        arrangement = outcome.arrangement
        arrangement.arrangement_id = arrangement_id
        if reference and not arrangement.reference:
            arrangement.reference = reference
        self.repository.save(arrangement, reason="upload_extracted")
        self.repository.record_event(
            arrangement_id,
            "document_ingested",
            details={
                "content_type": content_type,
                "filename": filename,
                "source_pages": ingested.page_count,
            },
        )
        return ExtractionResult(
            arrangement_id=arrangement_id,
            arrangement=arrangement,
            confidence=outcome.confidence,
            confidence_label=outcome.confidence_label,
            source_pages=ingested.page_count,
            extraction_model=outcome.model,
        )

    def extract_text(
        self,
        *,
        arrangement_id: str,
        text: str,
        reference: str | None = None,
    ) -> ExtractionResult:
        outcome = self.extractor.extract(text)
        arrangement = outcome.arrangement
        arrangement.arrangement_id = arrangement_id
        if reference and not arrangement.reference:
            arrangement.reference = reference
        self.repository.save(arrangement, reason="text_draft_created")
        self.repository.record_event(
            arrangement_id,
            "text_draft_created",
            details={"character_count": len(text)},
        )
        return ExtractionResult(
            arrangement_id=arrangement_id,
            arrangement=arrangement,
            confidence=outcome.confidence,
            confidence_label=outcome.confidence_label,
            source_pages=1,
            extraction_model=outcome.model,
        )

    def continue_clarification(self, *, arrangement_id: str, user_message: str):
        return handle_chat_turn(
            arrangement_id=arrangement_id,
            user_message=user_message,
            repository=self.repository,
        )


@dataclass(frozen=True)
class ChatOrchestratorAgent:
    qa_service: QAService
    repository: ArrangementRepository
    extraction_specialist: ExtractionSpecialistAgent

    def respond(self, *, session_id: str, message: str) -> ApiChatResponse:
        user_message = message.strip()

        if is_off_topic(user_message):
            return ApiChatResponse(
                session_id=session_id,
                mode="off_topic",
                reply=off_topic_reply(),
                arrangement=self.repository.get(session_id),
            )

        arrangement = self.repository.get(session_id)
        if arrangement is None:
            answer = self.qa_service.answer(user_message)
            self.repository.record_event(
                session_id,
                "qa_answered",
                details={"model": answer.model},
            )
            return ApiChatResponse(
                session_id=session_id,
                mode="qa",
                reply=answer.answer,
                arrangement=None,
            )

        response = self.extraction_specialist.continue_clarification(
            arrangement_id=session_id,
            user_message=user_message,
        )
        return ApiChatResponse(
            session_id=session_id,
            mode="clarification",
            reply=response.reply,
            arrangement=response.arrangement,
            clarifications=response.clarifications,
        )


@dataclass(frozen=True)
class AgentRuntime:
    chat_agent: ChatOrchestratorAgent
    extraction_agent: ExtractionSpecialistAgent


def build_agent_runtime(
    *,
    ingestion: DocumentIngestionService,
    extractor: ExtractionAgent,
    repository: ArrangementRepository,
    qa_service: QAService,
) -> AgentRuntime:
    extraction_specialist = ExtractionSpecialistAgent(
        ingestion=ingestion,
        extractor=extractor,
        repository=repository,
    )
    chat_agent = ChatOrchestratorAgent(
        qa_service=qa_service,
        repository=repository,
        extraction_specialist=extraction_specialist,
    )
    return AgentRuntime(
        chat_agent=chat_agent,
        extraction_agent=extraction_specialist,
    )
