"""Azure OpenAI-backed extraction of MDR arrangement data from raw text.

The extraction agent prompts the LLM to return a strict JSON payload
matching ``MDRArrangement``. For local development (no Azure OpenAI
endpoint configured) a heuristic extractor is used so the clarification
loop can still be exercised.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

from ..config import Settings
from ..models import MDRArrangement

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an MDR (Mandatory Disclosure Rules) extraction agent for the EY Tax team.
Given the full text of a tax arrangement document, extract a structured JSON object
that conforms to the following schema:

{
  "reference": string|null,
  "summary": string|null,
  "implementation_date": ISO-8601 date|null,
  "value": number|null,
  "currency": ISO-4217 code|null,
  "main_benefit_test": boolean|null,
  "hallmarks": [{ "code": string, "category": "A"|"B"|"C"|"D"|"E", "description": string|null }],
  "parties": [{ "role": "intermediary"|"relevant_taxpayer"|"associated_enterprise",
                "name": string|null, "tax_identification_number": string|null,
                "jurisdiction": ISO-3166 alpha-2|null, "address": string|null }],
  "jurisdictions": [ISO-3166 alpha-2, ...]
}

Rules:
- Return ONLY valid JSON, no commentary.
- Use null for fields you cannot confidently extract.
- Never fabricate names, TINs, dates, or hallmark codes.
"""


@dataclass(frozen=True)
class ExtractionOutcome:
    arrangement: MDRArrangement
    confidence: float
    model: str


class ExtractionAgent(Protocol):
    def extract(self, text: str) -> ExtractionOutcome: ...


class HeuristicExtractionAgent:
    """Lightweight regex-based fallback used when Azure OpenAI is not wired up."""

    MODEL_NAME = "heuristic-local"

    def extract(self, text: str) -> ExtractionOutcome:
        reference = self._find(r"\b(?:Reference|Ref|Arrangement\s*ID)\s*[:#]?\s*([A-Z0-9\-]+)", text)
        summary = self._first_paragraph(text)
        hallmark_codes = re.findall(r"\bhallmark\s+([A-E]\d[a-z]{0,2})\b", text, flags=re.I)
        hallmarks = [
            {"code": code.upper(), "category": code[0].upper(), "description": None}
            for code in sorted(set(hallmark_codes))
        ]
        jurisdictions = sorted(set(re.findall(r"\b([A-Z]{2})\b", text)))
        implementation = self._find(
            r"\bimplementation\s+date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", text
        )

        arrangement = MDRArrangement(
            reference=reference,
            summary=summary,
            implementation_date=implementation,  # type: ignore[arg-type]
            hallmarks=hallmarks,  # type: ignore[arg-type]
            jurisdictions=[j for j in jurisdictions if j.isalpha()][:5],
        )
        return ExtractionOutcome(
            arrangement=arrangement,
            confidence=0.35 if summary else 0.15,
            model=self.MODEL_NAME,
        )

    @staticmethod
    def _find(pattern: str, text: str) -> str | None:
        m = re.search(pattern, text, flags=re.I)
        return m.group(1).strip() if m else None

    @staticmethod
    def _first_paragraph(text: str) -> str | None:
        for block in text.split("\n\n"):
            block = block.strip()
            if len(block) > 40:
                return block[:600]
        return None


class AzureOpenAIExtractionAgent:
    """Real extraction via Azure OpenAI chat completions."""

    def __init__(self, settings: Settings) -> None:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        self._client = AzureOpenAI(
            azure_endpoint=settings.openai_endpoint,
            api_version=settings.openai_api_version,
            azure_ad_token_provider=token_provider,
        )
        self._deployment = settings.openai_deployment

    def extract(self, text: str) -> ExtractionOutcome:
        response = self._client.chat.completions.create(
            model=self._deployment,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text[:120_000]},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Extraction returned non-JSON payload; falling back to empty")
            payload = {}

        arrangement = MDRArrangement.model_validate(payload)
        filled = sum(
            1
            for v in (
                arrangement.reference,
                arrangement.summary,
                arrangement.implementation_date,
                arrangement.hallmarks or None,
                arrangement.parties or None,
                arrangement.jurisdictions or None,
            )
            if v
        )
        confidence = round(filled / 6.0, 2)
        return ExtractionOutcome(
            arrangement=arrangement, confidence=confidence, model=self._deployment
        )


def build_extraction_agent(settings: Settings) -> ExtractionAgent:
    if settings.azure_enabled:
        logger.info("Using Azure OpenAI extraction agent (%s)", settings.openai_deployment)
        return AzureOpenAIExtractionAgent(settings)
    logger.info("Using heuristic extraction agent (local fallback)")
    return HeuristicExtractionAgent()
