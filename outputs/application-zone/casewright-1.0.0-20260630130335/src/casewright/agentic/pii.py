"""PII detection / redaction service for the agentic RAG engine.

Ported from case-assistant-agent but reimplemented with the *synchronous* Azure AI Language
client and Casewright's managed-identity credential (``AzureKeyCredential`` only if an explicit
key is configured). Used as a guard on inbound queries and, optionally, on generated answers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from casewright.core.clients import get_credential
from casewright.core.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_PII_CATEGORIES: tuple[str, ...] = (
    "Person",
    "PersonType",
    "Email",
    "PhoneNumber",
    "Address",
    "IPAddress",
    "URL",
    "Organization",
    "USSocialSecurityNumber",
    "CreditCardNumber",
    "ABARoutingNumber",
    "InternationalBankingAccountNumber",
    "SWIFTCode",
)


@dataclass
class PIIEntity:
    text: str
    category: str
    offset: int
    length: int
    confidence_score: float
    subcategory: str | None = None


@dataclass
class PIIDetectionResult:
    entities: list[PIIEntity] = field(default_factory=list)
    redacted_text: str = ""
    original_length: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def contains_pii(self) -> bool:
        return len(self.entities) > 0


class PIIDetectionService:
    """Synchronous PII detection backed by Azure AI Language (Text Analytics)."""

    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client

        s = get_settings()
        if not s.pii_endpoint:
            raise RuntimeError("PII detection requested but PII_LANGUAGE_ENDPOINT is not configured")

        from azure.ai.textanalytics import TextAnalyticsClient

        self._client = TextAnalyticsClient(endpoint=s.pii_endpoint, credential=get_credential())
        return self._client

    def detect_pii(self, text: str) -> PIIDetectionResult:
        """Detect PII entities in ``text`` and return entities + redacted text."""
        if not text or not text.strip():
            return PIIDetectionResult(redacted_text=text, original_length=len(text))

        s = get_settings()
        client = self._ensure_client()

        response = client.recognize_pii_entities([text], language=s.pii_language)
        doc = response[0]

        if getattr(doc, "is_error", False):
            err = getattr(doc, "error", None)
            message = getattr(err, "message", "unknown error")
            logger.warning("PII detection returned an error: %s", message)
            return PIIDetectionResult(
                redacted_text=text, original_length=len(text), warnings=[str(message)]
            )

        min_conf = s.pii_min_confidence
        entities = [
            PIIEntity(
                text=e.text,
                category=e.category,
                subcategory=getattr(e, "subcategory", None),
                offset=e.offset,
                length=e.length,
                confidence_score=e.confidence_score,
            )
            for e in doc.entities
            if e.confidence_score >= min_conf
        ]

        return PIIDetectionResult(
            entities=entities,
            redacted_text=getattr(doc, "redacted_text", text),
            original_length=len(text),
        )

    def contains_pii(self, text: str) -> bool:
        return self.detect_pii(text).contains_pii

    def redact_pii(self, text: str) -> str:
        return self.detect_pii(text).redacted_text

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None
