"""MDR-specific Q&A service.

The BRD calls out MDR-specific Q&A as a first-class capability alongside
the two arrangement-creation flows. This service answers open-ended
questions about Mandatory Disclosure Rules (DAC6 hallmark categories,
reporting obligations, timing, etc.) with a grounded Azure OpenAI
prompt. A deterministic local fallback returns a canned snippet for
common topics so the endpoint is usable in tests and during local
development.
"""
from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from typing import Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from ..config import Settings

logger = logging.getLogger(__name__)


QA_SYSTEM_PROMPT = """You are an MDR (Mandatory Disclosure Rules) subject-matter assistant
for the EY Tax team. You answer questions about DAC6 / OECD MDR reporting,
hallmark categories A-E, intermediary vs relevant-taxpayer obligations,
timing of disclosure, and the main-benefit test.

Rules:
- Be concise (<= 6 sentences).
- Cite the hallmark or rule category when relevant (e.g. "Hallmark C1bi").
- If the question is outside MDR/DAC6 scope, say so plainly.
- Never invent case law, statute references, or client data.
"""


# Minimal local knowledge base used by the offline fallback. Keys are
# matched as case-insensitive substrings against the incoming question.
LOCAL_SNIPPETS: dict[str, str] = {
    "hallmark": (
        "DAC6 / MDR uses five hallmark categories (A-E). Categories A and B are "
        "subject to the main-benefit test; category C covers cross-border "
        "transactions, D covers automatic exchange and beneficial ownership "
        "circumvention, and E covers transfer pricing."
    ),
    "main benefit": (
        "The main-benefit test is met when the principal benefit (or one of the "
        "principal benefits) a person may reasonably expect to derive from an "
        "arrangement is a tax advantage. Only hallmarks A, B, and parts of C "
        "require it."
    ),
    "intermediary": (
        "An intermediary is any person who designs, markets, organises, makes "
        "available for implementation, or manages the implementation of a "
        "reportable cross-border arrangement. Reporting obligations generally "
        "shift to the relevant taxpayer if legal professional privilege applies."
    ),
    "deadline": (
        "Intermediaries must file within 30 days beginning the day after the "
        "arrangement is made available, ready for implementation, or the first "
        "step of implementation has been made - whichever is earlier."
    ),
    "relevant taxpayer": (
        "A relevant taxpayer is any person to whom a reportable cross-border "
        "arrangement is made available, who is ready to implement it, or who "
        "has implemented the first step. They must disclose when no "
        "intermediary is involved or when privilege blocks intermediary filing."
    ),
}


@dataclass(frozen=True)
class QAAnswer:
    question: str
    answer: str
    model: str


class QAService(Protocol):
    def answer(self, question: str) -> QAAnswer: ...


class LocalQAService:
    """Offline fallback keyed to MDR-specific substrings."""

    MODEL_NAME = "local-mdr-kb"

    def answer(self, question: str) -> QAAnswer:
        q = question.lower()
        for needle, snippet in LOCAL_SNIPPETS.items():
            if needle in q:
                return QAAnswer(question=question, answer=snippet, model=self.MODEL_NAME)
        return QAAnswer(
            question=question,
            answer=(
                "I can help with DAC6 / MDR topics such as hallmark categories, "
                "the main-benefit test, intermediary versus relevant-taxpayer "
                "obligations, and disclosure timing. Please rephrase the "
                "question toward one of those areas."
            ),
            model=self.MODEL_NAME,
        )


class AzureOpenAIQAService:
    """Grounded Q&A via Azure OpenAI chat completions."""

    def __init__(self, settings: Settings) -> None:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        self._credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            self._credential,
            "https://cognitiveservices.azure.com/.default",
        )
        self._client = AzureOpenAI(
            azure_endpoint=settings.openai_endpoint,
            api_version=settings.openai_api_version,
            azure_ad_token_provider=token_provider,
        )
        self._deployment = settings.openai_deployment
        self._embeddings_deployment = settings.openai_embeddings_deployment
        self._search_endpoint = settings.ai_search_endpoint.rstrip("/")
        self._search_index = settings.ai_search_index_name
        self._search_vector_field = settings.ai_search_vector_field
        self._search_semantic_configuration = settings.ai_search_semantic_configuration
        self._search_key = settings.ai_search_api_key

    def _build_vector_query(self, question: str) -> list[float] | None:
        try:
            response = self._client.embeddings.create(
                model=self._embeddings_deployment,
                input=question[:4000],
            )
        except Exception as exc:  # pragma: no cover - depends on Azure services
            logger.warning(
                "Embedding generation failed, continuing with semantic search: %s",
                exc,
            )
            return None

        if not response.data:
            return None
        return list(response.data[0].embedding)

    def _retrieve_context(self, question: str) -> str:
        if not (self._search_endpoint and self._search_index):
            return ""

        vector = self._build_vector_query(question)
        payload: dict[str, object] = {
            "search": question,
            "top": 3,
            "queryType": "semantic",
            "semanticConfiguration": self._search_semantic_configuration,
            "select": "title,content,source,category",
        }
        if vector:
            payload["vectorQueries"] = [
                {
                    "kind": "vector",
                    "vector": vector,
                    "fields": self._search_vector_field,
                    "k": 5,
                }
            ]

        url = (
            f"{self._search_endpoint}/indexes/{self._search_index}/docs/search"
            "?api-version=2024-07-01"
        )
        body = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
        }
        if self._search_key:
            headers["api-key"] = self._search_key
        else:
            token = self._credential.get_token("https://search.azure.com/.default")
            headers["Authorization"] = f"Bearer {token.token}"

        req = urllib_request.Request(
            url=url,
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib_error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning("AI Search retrieval failed, continuing without RAG context: %s", exc)
            return ""

        snippets: list[str] = []
        for item in payload.get("value", [])[:3]:
            content = item.get("content") or item.get("text") or item.get("chunk")
            if content:
                snippets.append(str(content)[:900])
        return "\n\n".join(snippets)

    def answer(self, question: str) -> QAAnswer:
        retrieval_context = self._retrieve_context(question)
        user_prompt = question[:4000]
        if retrieval_context:
            user_prompt = (
                f"Question:\n{question[:3000]}\n\n"
                "Retrieved MDR context:\n"
                f"{retrieval_context[:4000]}\n\n"
                "Answer using only this context when possible. "
                "If context is insufficient, state uncertainty clearly."
            )

        response = self._client.chat.completions.create(
            model=self._deployment,
            temperature=0.2,
            messages=[
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        return QAAnswer(question=question, answer=content, model=self._deployment)


def build_qa_service(settings: Settings) -> QAService:
    if settings.azure_enabled:
        logger.info("Using Azure OpenAI Q&A service (%s)", settings.openai_deployment)
        return AzureOpenAIQAService(settings)
    logger.info("Using local MDR Q&A fallback")
    return LocalQAService()
