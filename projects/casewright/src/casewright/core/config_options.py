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


# ---------------------------------------------------------------------------
# Per-service options (typed views over Settings)
#
# These plain ``BaseModel`` types give the service layer a stable, typed,
# grouped surface that is decoupled from the env-var field names on
# :class:`casewright.core.settings.Settings`. They are managed-identity-only by
# design: there are deliberately no ``api_key`` / ``connection_string`` fields,
# preserving Casewright's no-secrets posture.
# ---------------------------------------------------------------------------


class SearchServiceOptions(BaseModel):
    """Azure AI Search indexing + retrieval options."""

    model_config = {"str_strip_whitespace": True}

    endpoint: str = ""
    index_name: str = "casewright-index"
    semantic_configuration_name: str = "casewright-semantic"
    min_reranker_score: float = 2.0
    top_k: int = 8
    chunk_size: int = 3000
    chunk_overlap: int = 500


class BlobStorageOptions(BaseModel):
    """Azure Blob Storage options (ingestion landing + knowledge store)."""

    model_config = {"str_strip_whitespace": True}

    account_url: str = ""
    ingestion_container: str = "ingestion"
    knowledge_store_container: str = "knowledge-store"
    resource_id: str = ""


class AIServicesOptions(BaseModel):
    """Azure AI Services (Cognitive Services) options for the multimodal skillset."""

    model_config = {"str_strip_whitespace": True}

    endpoint: str = ""
    image_verbalization_enabled: bool = True


class AzureOpenAIOptions(BaseModel):
    """Azure OpenAI options for embeddings and chat completions."""

    model_config = {"str_strip_whitespace": True}

    endpoint: str = ""
    chat_deployment: str = "gpt-4o"
    embedding_deployment: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072


class CosmosDBOptions(BaseModel):
    """Azure Cosmos DB options for chat history + sync state."""

    model_config = {"str_strip_whitespace": True}

    endpoint: str = ""
    database: str = "casewright"
    history_container: str = "chat-history"
    sync_state_container: str = "sync-state"


class ServiceBusOptions(BaseModel):
    """Azure Service Bus options for the SharePoint sync queue."""

    model_config = {"str_strip_whitespace": True}

    fully_qualified_namespace: str = ""
    queue_name: str = "sharepoint-sync"


class GraphOptions(BaseModel):
    """Microsoft Graph (SharePoint) connection options."""

    model_config = {"str_strip_whitespace": True}

    tenant_id: str = ""
    client_id: str = ""


class APIOptions(BaseModel):
    """API auth / on-behalf-of (delegated Graph access) options."""

    model_config = {"str_strip_whitespace": True}

    require_jwt_validation: bool = False
    obo_enabled: bool = False
    obo_graph_scope: str = "https://graph.microsoft.com/.default"
    auth_audience: str = ""
    allowed_app_client_ids: str = ""


class WorkflowOptions(BaseModel):
    """Agentic RAG workflow tuning options (HyDE + reflection + cited answers)."""

    model_config = {"str_strip_whitespace": True}

    enabled: bool = True
    max_retrieval_iterations: int = 3
    chat_history_window: int = 5
    enable_query_rewriting: bool = True
    enable_reflection: bool = True
    hyde_temperature: float = 0.3
    hyde_max_tokens: int = 500
    answer_temperature: float = 0.1
    answer_max_tokens: int = 4096
    search_top_k: int = 10
    reflection_high_validity_threshold: float = 0.8
    reflection_moderate_validity_threshold: float = 0.6
    reflection_moderate_validity_min_count: int = 3


class PIIDetectionOptions(BaseModel):
    """Azure AI Language PII detection / redaction options."""

    model_config = {"str_strip_whitespace": True}

    enabled: bool = False
    endpoint: str = ""
    mode: str = "detect"  # off | detect | redact | block
    block_on_detection: bool = False
    redact_responses: bool = False
    language: str = "en"
    min_confidence: float = 0.0


class FoundryAgentOptions(BaseModel):
    """Azure AI Foundry hosted prompt-agent options."""

    model_config = {"str_strip_whitespace": True}

    enabled: bool = False
    project_endpoint: str = ""
    agent_id: str = ""
    kb_connection_name: str = "casewright-kb-mcp"


class AppConfigurationOptions(BaseModel):
    """Azure App Configuration bootstrap options."""

    model_config = {"str_strip_whitespace": True}

    enabled: bool = False
    endpoint: str = ""
    key_filter: str = "*"
    label_filter: str = ""
