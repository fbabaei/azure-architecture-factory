"""Casewright central configuration.

All tunables are sourced from environment variables so a model swap, index rename, or
endpoint change never requires a code edit. No secrets are hardcoded; managed identity is
used for every Azure hop, so most settings are endpoints/resource ids, not keys.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from casewright.core.config_options import KnowledgeBaseOptions, KnowledgeSourceOptions

# Default resource names for the Foundry IQ knowledge base + its bound source.
KB_NAME = "casewright-kb"
KS_NAME = "casewright-ks"

_DEFAULT_KB_DESCRIPTION = (
    "Casewright case-knowledge base over SharePoint-sourced case documents indexed in "
    "Azure AI Search. Use it to answer questions grounded strictly in those documents."
)
_DEFAULT_KB_RETRIEVAL_INSTRUCTIONS = (
    "You are an AI agent responsible for evaluating and prioritizing documents ingested from "
    "SharePoint case sites.\n\n"
    "CRITICAL PRECONDITION:\n"
    "- A valid SharePoint site name (case site identifier) MUST be provided as input.\n"
    "- If no site name is provided, you MUST NOT perform any processing, scoring, retrieval, or "
    "output generation.\n"
    "- In such cases, return no results and take no action.\n\n"
    "Your objective is to identify and rank the most \"valuable\" documents using file metadata and "
    "derived signals. You must assign a usefulness score to each document and enable downstream "
    "retrieval systems to prioritize high-value content.\n\n"
    "Key responsibilities:\n\n"
    "1. Metadata-Based Evaluation\n"
    "Analyze the following properties for every document:\n"
    "- File name\n"
    "- File path (folder structure)\n"
    "- Last modified date\n"
    "- File size\n"
    "- Case project name (external reference tied to the site)\n\n"
    "2. Scoping Constraint\n"
    "- Only evaluate documents that belong to the provided SharePoint site\n"
    "- Do not process or consider documents from any other site\n"
    "- Use the site name to ensure proper case/project alignment\n\n"
    "3. Scoring Logic\n\n"
    "File Name:\n"
    "- Reward indicators such as \"final\", version markers (vN, vFinal), or date prefixes\n"
    "- Penalize junk patterns, temporary files, or irrelevant naming\n"
    "- Extract version and project identifiers where possible\n"
    "- Detect cross-project references and penalize mismatches\n\n"
    "File Path:\n"
    "- Reward files located in high-value folders (e.g., \"Key Presentations\", \"Final Documents\")\n"
    "- Penalize files in low-value folders (e.g., \"working\", \"wip\", \"backup\", \"template\")\n"
    "- Apply penalties for deeply nested paths (>5 levels)\n\n"
    "Last Modified Date:\n"
    "- Validate consistency between filename dates and actual modification timestamps\n"
    "- Reward recency and alignment with naming signals\n\n"
    "File Size:\n"
    "- Assign proportional value relative to the largest files in the dataset\n"
    "- Larger files may indicate more complete deliverables (e.g., final presentations)\n\n"
    "Case Project Name Matching:\n"
    "- Reward alignment between file name and expected case/project identifier derived from the site\n"
    "- Penalize documents associated with different projects (cross-project contamination)\n\n"
    "4. Pre-Filtering\n"
    "Exclude:\n"
    "- Temporary, system, or lock files\n"
    "- Files with irrelevant extensions or naming patterns\n"
    "- Content from disallowed folders (e.g., early-stage or non-curated directories such as "
    "folders 1-3)\n"
    "- Only allow ingestion from approved folders (e.g., folders 4-5)\n\n"
    "5. Output\n"
    "- Assign a numerical \"usefulness score\" to each document\n"
    "- Attach the score as metadata to each indexed record\n"
    "- Ensure scores are updated when documents are modified or new versions are added\n\n"
    "6. Indexing Behavior\n"
    "- Operate at the document level but support chunk-level indexing downstream\n"
    "- Preserve all relevant SharePoint metadata\n"
    "- Ensure outputs are optimized for retrieval in AI search systems\n\n"
    "7. Continuous Improvement\n"
    "- Allow scoring logic to evolve over time\n"
    "- Support integration of content-based signals (e.g., AI-derived insights) in addition to "
    "metadata\n\n"
    "Your decisions must be deterministic, explainable, and strictly scoped to the provided "
    "SharePoint site."
)
_DEFAULT_KS_DESCRIPTION = (
    "Search-index knowledge source over the Casewright case-document index."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Azure AI Search ---
    search_endpoint: str = Field("", alias="SEARCHSERVICE_ENDPOINT")
    search_index_name: str = Field("casewright-index", alias="SEARCH_INDEX_NAME")
    semantic_configuration_name: str = Field("casewright-semantic", alias="SEARCH_SEMANTIC_CONFIGURATION")
    min_reranker_score: float = Field(2.0, alias="SEARCH_MIN_RERANKER_SCORE")
    search_top_k: int = Field(8, alias="SEARCH_TOP_K")
    chunk_size: int = Field(3000, alias="INGESTION_CHUNK_SIZE")
    chunk_overlap: int = Field(500, alias="INGESTION_CHUNK_OVERLAP")

    # --- Foundry IQ knowledge base (agentic retrieval; preview REST) ---
    search_kb_api_version: str = Field("2025-11-01-preview", alias="SEARCH_KB_API_VERSION")
    kb_name: str = Field(KB_NAME, alias="SEARCH_KB_NAME")
    kb_source_name: str = Field(KS_NAME, alias="SEARCH_KB_KS_NAME")
    kb_description: str = Field(_DEFAULT_KB_DESCRIPTION, alias="SEARCH_KB_DESCRIPTION")
    kb_aoai_endpoint: str = Field("", alias="SEARCH_KB_AOAI_ENDPOINT")
    kb_aoai_deployment_name: str = Field("", alias="SEARCH_KB_AOAI_DEPLOYMENT_NAME")
    kb_output_modality: str = Field("extractiveData", alias="SEARCH_KB_OUTPUT_MODALITY")
    kb_retrieval_reasoning_effort: str = Field("medium", alias="SEARCH_KB_RETRIEVAL_REASONING_EFFORT")
    kb_retrieval_instructions: str = Field(
        _DEFAULT_KB_RETRIEVAL_INSTRUCTIONS, alias="SEARCH_KB_RETRIEVAL_INSTRUCTIONS"
    )
    kb_default_reranker_threshold: float = Field(2.0, alias="SEARCH_KB_DEFAULT_RERANKER_THRESHOLD")
    kb_max_output_size: int = Field(5000, alias="SEARCH_KB_MAX_OUTPUT_SIZE")
    kb_attempt_fast_path: bool = Field(True, alias="SEARCH_KB_ATTEMPT_FAST_PATH")
    kb_ks_index_name: str = Field("", alias="SEARCH_KB_KS_INDEX_NAME")
    kb_ks_description: str = Field(_DEFAULT_KS_DESCRIPTION, alias="SEARCH_KB_KS_DESCRIPTION")
    kb_ks_source_data_fields: list[str] = Field(default_factory=list, alias="SEARCH_KB_KS_SOURCE_DATA_FIELDS")
    kb_ks_search_fields: list[str] = Field(default_factory=list, alias="SEARCH_KB_KS_SEARCH_FIELDS")
    kb_ks_semantic_configuration_name: str = Field("", alias="SEARCH_KB_KS_SEMANTIC_CONFIGURATION_NAME")
    foundry_kb_connection_name: str = Field("casewright-kb-mcp", alias="FOUNDRY_KB_CONNECTION_NAME")

    # --- Azure OpenAI ---
    openai_endpoint: str = Field("", alias="AZURE_OPENAI_ENDPOINT")
    chat_deployment: str = Field("gpt-4o", alias="AZURE_OPENAI_CHAT_DEPLOYMENT")
    embedding_deployment: str = Field("text-embedding-3-large", alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    embedding_dimensions: int = Field(3072, alias="AZURE_OPENAI_EMBEDDING_DIMENSIONS")

    # --- Storage (ingestion landing + knowledge store) ---
    blob_account_url: str = Field("", alias="BLOBSTORAGE_ACCOUNT_URL")
    ingestion_container: str = Field("ingestion", alias="INGESTION_CONTAINER")
    knowledge_store_container: str = Field("knowledge-store", alias="KNOWLEDGE_STORE_CONTAINER")

    # --- Cosmos DB ---
    cosmos_endpoint: str = Field("", alias="COSMOS_ENDPOINT")
    cosmos_database: str = Field("casewright", alias="COSMOS_DATABASE")
    cosmos_history_container: str = Field("chat-history", alias="COSMOS_HISTORY_CONTAINER")
    cosmos_sync_state_container: str = Field("sync-state", alias="COSMOS_SYNC_STATE_CONTAINER")

    # --- Service Bus ---
    servicebus_namespace: str = Field("", alias="SERVICEBUS_FULLY_QUALIFIED_NAMESPACE")
    servicebus_queue_name: str = Field("sharepoint-sync", alias="SERVICEBUS_QUEUE_NAME")

    # --- Microsoft Graph (SharePoint) ---
    graph_tenant_id: str = Field("", alias="GRAPH_TENANT_ID")
    graph_client_id: str = Field("", alias="GRAPH_CLIENT_ID")
    graph_client_secret: str = Field("", alias="GRAPH_CLIENT_SECRET")

    # --- API auth / on-behalf-of (delegated Graph access) ---
    # When disabled (default), inbound requests are not validated and SharePoint read calls run
    # under the app/managed identity, preserving the connectivity-free import + dev experience.
    api_require_jwt_validation: bool = Field(False, alias="API_REQUIRE_JWT_VALIDATION")
    api_obo_enabled: bool = Field(False, alias="API_OBO_ENABLED")
    api_obo_graph_scope: str = Field(
        "https://graph.microsoft.com/.default", alias="API_OBO_GRAPH_SCOPE"
    )
    api_auth_audience: str = Field("", alias="API_AUTH_AUDIENCE")
    api_allowed_app_client_ids: str = Field("", alias="API_ALLOWED_APP_CLIENT_IDS")

    @property
    def auth_audiences(self) -> set[str]:
        """Accepted token audiences: explicit audience plus the Graph client id (api://<id> form)."""
        values: set[str] = set()
        for raw in (self.api_auth_audience, self.graph_client_id):
            value = (raw or "").strip()
            if value:
                values.add(value)
                if not value.startswith("api://") and "://" not in value:
                    values.add(f"api://{value}")
        return values

    @property
    def allowed_app_client_ids(self) -> set[str]:
        return {p.strip() for p in (self.api_allowed_app_client_ids or "").split(",") if p.strip()}

    # --- Azure AI Foundry (optional hosted prompt-agent) ---
    foundry_project_endpoint: str = Field("", alias="FOUNDRY_PROJECT_ENDPOINT")
    foundry_agent_id: str = Field("", alias="FOUNDRY_AGENT_ID")

    # --- Scheduler ---
    sharepoint_sync_schedule: str = Field("0 0 */6 * * *", alias="SHAREPOINT_SYNC_SCHEDULE")
    sync_default_tenant_id: str = Field("", alias="SYNC_DEFAULT_TENANT_ID")

    # --- Agentic RAG workflow (HyDE + reflection + cited answer generation) ---
    agentic_enabled: bool = Field(True, alias="AGENTIC_ENABLED")
    workflow_max_retrieval_iterations: int = Field(3, alias="WORKFLOW_MAX_RETRIEVAL_ITERATIONS")
    workflow_chat_history_window: int = Field(5, alias="WORKFLOW_CHAT_HISTORY_WINDOW")
    workflow_enable_query_rewriting: bool = Field(True, alias="WORKFLOW_ENABLE_QUERY_REWRITING")
    workflow_enable_reflection: bool = Field(True, alias="WORKFLOW_ENABLE_REFLECTION")
    workflow_hyde_temperature: float = Field(0.3, alias="WORKFLOW_HYDE_TEMPERATURE")
    workflow_hyde_max_tokens: int = Field(500, alias="WORKFLOW_HYDE_MAX_TOKENS")
    workflow_answer_temperature: float = Field(0.1, alias="WORKFLOW_ANSWER_TEMPERATURE")
    workflow_answer_max_tokens: int = Field(4096, alias="WORKFLOW_ANSWER_MAX_TOKENS")
    workflow_search_top_k: int = Field(10, alias="WORKFLOW_SEARCH_TOP_K")
    reflection_high_validity_threshold: float = Field(0.8, alias="WORKFLOW_REFLECTION_HIGH_VALIDITY_THRESHOLD")
    reflection_moderate_validity_threshold: float = Field(0.6, alias="WORKFLOW_REFLECTION_MODERATE_VALIDITY_THRESHOLD")
    reflection_moderate_validity_min_count: int = Field(3, alias="WORKFLOW_REFLECTION_MODERATE_VALIDITY_MIN_COUNT")

    # --- PII detection / redaction (Azure AI Language) ---
    pii_enabled: bool = Field(False, alias="PII_ENABLED")
    pii_endpoint: str = Field("", alias="PII_LANGUAGE_ENDPOINT")
    pii_mode: str = Field("detect", alias="PII_MODE")  # off | detect | redact | block
    pii_block_on_detection: bool = Field(False, alias="PII_BLOCK_ON_DETECTION")
    pii_redact_responses: bool = Field(False, alias="PII_REDACT_RESPONSES")
    pii_language: str = Field("en", alias="PII_LANGUAGE")
    pii_min_confidence: float = Field(0.0, alias="PII_MIN_CONFIDENCE")

    @property
    def foundry_enabled(self) -> bool:
        return bool(self.foundry_project_endpoint and self.foundry_agent_id)

    @property
    def pii_active(self) -> bool:
        return bool(self.pii_enabled and self.pii_endpoint)

    @property
    def kb_mcp_endpoint(self) -> str:
        """MCP server URL exposed by the knowledge base for agentic retrieval."""
        base = self.search_endpoint.rstrip("/")
        return f"{base}/knowledgebases/{self.kb_name}/mcp?api-version={self.search_kb_api_version}"

    @property
    def knowledge_base_options(self) -> KnowledgeBaseOptions:
        """Build the provisioning options for the knowledge base + its source.

        AOAI endpoint/deployment and the source index/semantic config fall back to the
        primary search + OpenAI settings so a minimal ``.env`` provisions correctly.
        """
        source = KnowledgeSourceOptions(
            name=self.kb_source_name,
            index_name=self.kb_ks_index_name or self.search_index_name,
            description=self.kb_ks_description or None,
            source_data_fields=list(self.kb_ks_source_data_fields),
            search_fields=list(self.kb_ks_search_fields),
            semantic_configuration_name=(
                self.kb_ks_semantic_configuration_name or self.semantic_configuration_name or None
            ),
        )
        return KnowledgeBaseOptions(
            name=self.kb_name,
            description=self.kb_description or None,
            knowledge_sources=[source],
            aoai_endpoint=(self.kb_aoai_endpoint or self.openai_endpoint).rstrip("/") or None,
            aoai_deployment_name=self.kb_aoai_deployment_name or self.chat_deployment or None,
            output_modality=self.kb_output_modality,  # type: ignore[arg-type]
            default_reranker_threshold=self.kb_default_reranker_threshold,
            max_output_size=self.kb_max_output_size,
            attempt_fast_path=self.kb_attempt_fast_path,
            retrieval_instructions=self.kb_retrieval_instructions or None,
            retrieval_reasoning_effort=self.kb_retrieval_reasoning_effort,  # type: ignore[arg-type]
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
