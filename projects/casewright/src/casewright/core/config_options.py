"""Provisioning option models for the Foundry IQ knowledge base.

These describe *what to provision* on Azure AI Search (a knowledge source bound
to the ``casewright-index`` plus a knowledge base that wraps it with an LLM for
agentic retrieval). They are deliberately separate from the API-surface models in
``models.py`` because they are deploy-time configuration, not request/response
shapes. Values are assembled from :class:`casewright.core.settings.Settings`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeSourceOptions(BaseModel):
    """A single knowledge source bound to an existing search index."""

    model_config = {"str_strip_whitespace": True}

    name: str = Field(min_length=1)
    kind: Literal["searchIndex"] = "searchIndex"
    index_name: str = Field(min_length=1)
    description: str | None = None
    source_data_fields: list[str] = Field(default_factory=list)
    search_fields: list[str] = Field(default_factory=list)
    semantic_configuration_name: str | None = None


class KnowledgeBaseOptions(BaseModel):
    """A knowledge base (agentic retrieval target) wrapping one or more sources."""

    model_config = {"str_strip_whitespace": True}

    name: str = "casewright-kb"
    description: str | None = None
    knowledge_sources: list[KnowledgeSourceOptions] = Field(default_factory=list)
    aoai_endpoint: str | None = None
    aoai_deployment_name: str | None = None
    output_modality: Literal["extractiveData", "answerSynthesis"] = "extractiveData"
    default_reranker_threshold: float = Field(default=2.0, ge=0, le=4)
    max_output_size: int = Field(default=5000, gt=0)
    attempt_fast_path: bool = True
    retrieval_instructions: str | None = None
    retrieval_reasoning_effort: Literal["minimal", "low", "medium"] = "medium"
