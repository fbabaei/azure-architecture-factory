"""Casewright central configuration.

All tunables are sourced from environment variables so a model swap, index rename, or
endpoint change never requires a code edit. No secrets are hardcoded; managed identity is
used for every Azure hop, so most settings are endpoints/resource ids, not keys.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from casewright.core.app_config_source import AppConfigAwareSettings
from casewright.core.config_options import (
    AIServicesOptions,
    APIOptions,
    AppConfigurationOptions,
    AzureOpenAIOptions,
    BlobStorageOptions,
    CosmosDBOptions,
    FoundryAgentOptions,
    GraphOptions,
    KnowledgeBaseOptions,
    KnowledgeSourceOptions,
    PIIDetectionOptions,
    SearchServiceOptions,
    ServiceBusOptions,
    WorkflowOptions,
)

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


class Settings(AppConfigAwareSettings):
    """Casewright application settings.

    Loaded from (highest → lowest priority): constructor kwargs, environment
    variables, Azure App Configuration (when ``APP_CONFIG_ENDPOINT`` is set),
    ``.env`` file, and the file-secrets directory. Every field is
    self-documenting via ``description=`` and managed-identity-only — there are
    no API-key or connection-string fields anywhere.

    Typed, grouped views are available via the ``*_options`` properties (e.g.
    :pyattr:`search_options`) which decouple the service layer from these
    env-var field names.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Azure App Configuration bootstrap (read from env/.env, never from the store) ---
    app_config_endpoint: str = Field(
        "", alias="APP_CONFIG_ENDPOINT",
        description="Azure App Configuration store endpoint URL (enables App Config loading via managed identity).",
    )
    app_config_key_filter: str = Field(
        "*", alias="APP_CONFIG_KEY_FILTER",
        description="Key prefix selector in the store (e.g. 'casewright:*'); the prefix is trimmed automatically.",
    )
    app_config_label_filter: str = Field(
        "", alias="APP_CONFIG_LABEL_FILTER",
        description="Environment label overlay (e.g. 'production'); falls back to ENVIRONMENT when unset.",
    )
    environment: str = Field(
        "development", alias="ENVIRONMENT",
        description="Deployment environment: development, staging, or production.",
    )

    # --- Azure AI Search ---
    search_endpoint: str = Field(
        "", alias="SEARCHSERVICE_ENDPOINT", description="Azure AI Search service endpoint URL."
    )
    search_index_name: str = Field(
        "casewright-index", alias="SEARCH_INDEX_NAME", description="Name of the search index."
    )
    semantic_configuration_name: str = Field(
        "casewright-semantic", alias="SEARCH_SEMANTIC_CONFIGURATION",
        description="Semantic ranking configuration name on the index.",
    )
    min_reranker_score: float = Field(
        2.0, alias="SEARCH_MIN_RERANKER_SCORE",
        description="Minimum reranker score (0-4) to retain a semantically ranked result.",
    )
    search_top_k: int = Field(
        8, alias="SEARCH_TOP_K", description="Default number of results to retrieve per search."
    )
    chunk_size: int = Field(
        3000, alias="INGESTION_CHUNK_SIZE", description="Maximum characters per chunk during ingestion split."
    )
    chunk_overlap: int = Field(
        500, alias="INGESTION_CHUNK_OVERLAP", description="Character overlap between adjacent chunks."
    )

    # --- Foundry IQ knowledge base (agentic retrieval; preview REST) ---
    search_kb_api_version: str = Field(
        "2025-11-01-preview", alias="SEARCH_KB_API_VERSION",
        description="Preview REST API version for the Foundry IQ knowledge base.",
    )
    kb_name: str = Field(KB_NAME, alias="SEARCH_KB_NAME", description="Knowledge base resource name.")
    kb_source_name: str = Field(
        KS_NAME, alias="SEARCH_KB_KS_NAME", description="Knowledge source resource name bound to the index."
    )
    kb_description: str = Field(
        _DEFAULT_KB_DESCRIPTION, alias="SEARCH_KB_DESCRIPTION", description="Human-readable knowledge base description."
    )
    kb_aoai_endpoint: str = Field(
        "", alias="SEARCH_KB_AOAI_ENDPOINT",
        description="Override AOAI endpoint for the KB; falls back to AZURE_OPENAI_ENDPOINT.",
    )
    kb_aoai_deployment_name: str = Field(
        "", alias="SEARCH_KB_AOAI_DEPLOYMENT_NAME",
        description="Override AOAI chat deployment for the KB; falls back to the chat deployment.",
    )
    kb_output_modality: str = Field(
        "extractiveData", alias="SEARCH_KB_OUTPUT_MODALITY",
        description="KB output modality: extractiveData or answerSynthesis.",
    )
    kb_retrieval_reasoning_effort: str = Field(
        "medium", alias="SEARCH_KB_RETRIEVAL_REASONING_EFFORT",
        description="KB query-planning reasoning effort: minimal, low, or medium.",
    )
    kb_retrieval_instructions: str = Field(
        _DEFAULT_KB_RETRIEVAL_INSTRUCTIONS, alias="SEARCH_KB_RETRIEVAL_INSTRUCTIONS",
        description="retrievalInstructions prompt used by the LLM during KB query planning.",
    )
    kb_default_reranker_threshold: float = Field(
        2.0, alias="SEARCH_KB_DEFAULT_RERANKER_THRESHOLD",
        description="Default minimum reranker score (0-4) for the KB.",
    )
    kb_max_output_size: int = Field(
        5000, alias="SEARCH_KB_MAX_OUTPUT_SIZE", description="Maximum output size per KB invocation."
    )
    kb_attempt_fast_path: bool = Field(
        True, alias="SEARCH_KB_ATTEMPT_FAST_PATH", description="Allow the KB to short-circuit query planning."
    )
    kb_ks_index_name: str = Field(
        "", alias="SEARCH_KB_KS_INDEX_NAME",
        description="Index backing the knowledge source; defaults to SEARCH_INDEX_NAME.",
    )
    kb_ks_description: str = Field(
        _DEFAULT_KS_DESCRIPTION, alias="SEARCH_KB_KS_DESCRIPTION", description="Knowledge source description."
    )
    kb_ks_source_data_fields: list[str] = Field(
        default_factory=list, alias="SEARCH_KB_KS_SOURCE_DATA_FIELDS",
        description="Index field names surfaced as citation metadata (KS sourceDataFields).",
    )
    kb_ks_search_fields: list[str] = Field(
        default_factory=list, alias="SEARCH_KB_KS_SEARCH_FIELDS",
        description="Index field names restricting which fields are searched (KS searchFields).",
    )
    kb_ks_semantic_configuration_name: str = Field(
        "", alias="SEARCH_KB_KS_SEMANTIC_CONFIGURATION_NAME",
        description="Override the index's default semantic configuration for the KS.",
    )
    foundry_kb_connection_name: str = Field(
        "casewright-kb-mcp", alias="FOUNDRY_KB_CONNECTION_NAME",
        description="Foundry connection name exposing the KB MCP endpoint.",
    )

    # --- Azure OpenAI ---
    openai_endpoint: str = Field(
        "", alias="AZURE_OPENAI_ENDPOINT", description="Azure OpenAI endpoint URL."
    )
    chat_deployment: str = Field(
        "gpt-4o", alias="AZURE_OPENAI_CHAT_DEPLOYMENT", description="Chat completion deployment name."
    )
    embedding_deployment: str = Field(
        "text-embedding-3-large", alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        description="Embedding model deployment name.",
    )
    embedding_dimensions: int = Field(
        3072, alias="AZURE_OPENAI_EMBEDDING_DIMENSIONS", description="Embedding vector dimensions."
    )

    # --- Storage (ingestion landing + knowledge store) ---
    blob_account_url: str = Field(
        "", alias="BLOBSTORAGE_ACCOUNT_URL", description="Azure Storage account blob endpoint URL."
    )
    ingestion_container: str = Field(
        "ingestion", alias="INGESTION_CONTAINER", description="Blob container for ingestion landing documents."
    )
    knowledge_store_container: str = Field(
        "knowledge-store", alias="KNOWLEDGE_STORE_CONTAINER",
        description="Blob container backing the skillset knowledge store (extracted images).",
    )
    storage_resource_id: str = Field(
        "", alias="STORAGE_RESOURCE_ID",
        description="Storage account ARM resource id used for the knowledge store managed-identity connection.",
    )

    # --- Azure AI Services (multimodal skillset: Document Intelligence layout + image verbalization) ---
    ai_services_endpoint: str = Field(
        "", alias="AI_SERVICES_ENDPOINT",
        description="Azure AI Services (Cognitive Services) endpoint attached to the multimodal skillset.",
    )
    image_verbalization_enabled: bool = Field(
        True, alias="IMAGE_VERBALIZATION_ENABLED",
        description="Generate GPT-vision descriptions + embeddings for extracted images during ingestion.",
    )

    # --- Cosmos DB ---
    cosmos_endpoint: str = Field(
        "", alias="COSMOS_ENDPOINT", description="Cosmos DB account endpoint URL."
    )
    cosmos_database: str = Field(
        "casewright", alias="COSMOS_DATABASE", description="Cosmos DB database name."
    )
    cosmos_history_container: str = Field(
        "chat-history", alias="COSMOS_HISTORY_CONTAINER", description="Container for chat history."
    )
    cosmos_sync_state_container: str = Field(
        "sync-state", alias="COSMOS_SYNC_STATE_CONTAINER", description="Container for SharePoint sync state."
    )

    # --- Service Bus ---
    servicebus_namespace: str = Field(
        "", alias="SERVICEBUS_FULLY_QUALIFIED_NAMESPACE",
        description="Service Bus fully-qualified namespace (e.g. <ns>.servicebus.windows.net).",
    )
    servicebus_queue_name: str = Field(
        "sharepoint-sync", alias="SERVICEBUS_QUEUE_NAME", description="Queue name for SharePoint sync messages."
    )

    # --- Microsoft Graph (SharePoint) ---
    graph_tenant_id: str = Field(
        "", alias="GRAPH_TENANT_ID", description="Entra tenant id for Microsoft Graph access."
    )
    graph_client_id: str = Field(
        "", alias="GRAPH_CLIENT_ID", description="App (client) id used for Microsoft Graph / token audience."
    )
    graph_client_secret: str = Field(
        "", alias="GRAPH_CLIENT_SECRET",
        description="Optional client secret for confidential-client Graph flows (prefer managed identity).",
    )

    # --- API auth / on-behalf-of (delegated Graph access) ---
    # When disabled (default), inbound requests are not validated and SharePoint read calls run
    # under the app/managed identity, preserving the connectivity-free import + dev experience.
    api_require_jwt_validation: bool = Field(
        False, alias="API_REQUIRE_JWT_VALIDATION",
        description="Validate inbound bearer tokens; when off, requests run under the app identity.",
    )
    api_obo_enabled: bool = Field(
        False, alias="API_OBO_ENABLED",
        description="Exchange the inbound user token for a Graph token via on-behalf-of.",
    )
    api_obo_graph_scope: str = Field(
        "https://graph.microsoft.com/.default", alias="API_OBO_GRAPH_SCOPE",
        description="Scope requested during the on-behalf-of token exchange.",
    )
    api_auth_audience: str = Field(
        "", alias="API_AUTH_AUDIENCE", description="Expected audience claim for inbound tokens."
    )
    api_allowed_app_client_ids: str = Field(
        "", alias="API_ALLOWED_APP_CLIENT_IDS",
        description="Comma-separated app client ids permitted to call the API.",
    )

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
    foundry_project_endpoint: str = Field(
        "", alias="FOUNDRY_PROJECT_ENDPOINT", description="Azure AI Foundry project endpoint URL."
    )
    foundry_agent_id: str = Field(
        "", alias="FOUNDRY_AGENT_ID", description="Identifier of the deployed Foundry prompt agent."
    )

    # --- Scheduler ---
    sharepoint_sync_schedule: str = Field(
        "0 0 */6 * * *", alias="SHAREPOINT_SYNC_SCHEDULE",
        description="NCRONTAB expression controlling the SharePoint sync timer trigger.",
    )
    sync_default_tenant_id: str = Field(
        "", alias="SYNC_DEFAULT_TENANT_ID", description="Default tenant id used when scheduling SharePoint syncs."
    )

    # --- Agentic RAG workflow (HyDE + reflection + cited answer generation) ---
    agentic_enabled: bool = Field(
        True, alias="AGENTIC_ENABLED", description="Enable the multi-step agentic RAG workflow."
    )
    workflow_max_retrieval_iterations: int = Field(
        3, alias="WORKFLOW_MAX_RETRIEVAL_ITERATIONS", description="Maximum retrieval/reflection loops per query."
    )
    workflow_chat_history_window: int = Field(
        5, alias="WORKFLOW_CHAT_HISTORY_WINDOW", description="Number of prior turns included as context."
    )
    workflow_enable_query_rewriting: bool = Field(
        True, alias="WORKFLOW_ENABLE_QUERY_REWRITING", description="Rewrite the user query before retrieval."
    )
    workflow_enable_reflection: bool = Field(
        True, alias="WORKFLOW_ENABLE_REFLECTION", description="Reflect on retrieved results to decide on re-retrieval."
    )
    workflow_hyde_temperature: float = Field(
        0.3, alias="WORKFLOW_HYDE_TEMPERATURE", description="Sampling temperature for HyDE hypothetical-document generation."
    )
    workflow_hyde_max_tokens: int = Field(
        500, alias="WORKFLOW_HYDE_MAX_TOKENS", description="Max tokens for HyDE generation."
    )
    workflow_answer_temperature: float = Field(
        0.1, alias="WORKFLOW_ANSWER_TEMPERATURE", description="Sampling temperature for final cited-answer generation."
    )
    workflow_answer_max_tokens: int = Field(
        4096, alias="WORKFLOW_ANSWER_MAX_TOKENS", description="Max tokens for the final answer."
    )
    workflow_search_top_k: int = Field(
        10, alias="WORKFLOW_SEARCH_TOP_K", description="Results retrieved per iteration inside the workflow."
    )
    reflection_high_validity_threshold: float = Field(
        0.8, alias="WORKFLOW_REFLECTION_HIGH_VALIDITY_THRESHOLD",
        description="Validity score (0-1) above which retrieval is accepted immediately.",
    )
    reflection_moderate_validity_threshold: float = Field(
        0.6, alias="WORKFLOW_REFLECTION_MODERATE_VALIDITY_THRESHOLD",
        description="Validity score (0-1) above which retrieval is accepted given enough results.",
    )
    reflection_moderate_validity_min_count: int = Field(
        3, alias="WORKFLOW_REFLECTION_MODERATE_VALIDITY_MIN_COUNT",
        description="Minimum result count required to accept a moderate-validity retrieval.",
    )

    # --- PII detection / redaction (Azure AI Language) ---
    pii_enabled: bool = Field(
        False, alias="PII_ENABLED", description="Enable PII detection/redaction via Azure AI Language."
    )
    pii_endpoint: str = Field(
        "", alias="PII_LANGUAGE_ENDPOINT", description="Azure AI Language endpoint URL for PII detection."
    )
    pii_mode: str = Field(
        "detect", alias="PII_MODE", description="PII handling mode: off, detect, redact, or block."
    )
    pii_block_on_detection: bool = Field(
        False, alias="PII_BLOCK_ON_DETECTION", description="Block the request when PII is detected."
    )
    pii_redact_responses: bool = Field(
        False, alias="PII_REDACT_RESPONSES", description="Redact detected PII from responses."
    )
    pii_language: str = Field(
        "en", alias="PII_LANGUAGE", description="ISO language code used for PII analysis."
    )
    pii_min_confidence: float = Field(
        0.0, alias="PII_MIN_CONFIDENCE", description="Minimum confidence (0-1) for a PII entity to count."
    )

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

    # ------------------------------------------------------------------
    # Typed, grouped views (decouple the service layer from env-var names)
    # ------------------------------------------------------------------

    @property
    def search_options(self) -> SearchServiceOptions:
        return SearchServiceOptions(
            endpoint=self.search_endpoint,
            index_name=self.search_index_name,
            semantic_configuration_name=self.semantic_configuration_name,
            min_reranker_score=self.min_reranker_score,
            top_k=self.search_top_k,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    @property
    def blob_storage_options(self) -> BlobStorageOptions:
        return BlobStorageOptions(
            account_url=self.blob_account_url,
            ingestion_container=self.ingestion_container,
            knowledge_store_container=self.knowledge_store_container,
            resource_id=self.storage_resource_id,
        )

    @property
    def ai_services_options(self) -> AIServicesOptions:
        return AIServicesOptions(
            endpoint=self.ai_services_endpoint,
            image_verbalization_enabled=self.image_verbalization_enabled,
        )

    @property
    def azure_openai_options(self) -> AzureOpenAIOptions:
        return AzureOpenAIOptions(
            endpoint=self.openai_endpoint,
            chat_deployment=self.chat_deployment,
            embedding_deployment=self.embedding_deployment,
            embedding_dimensions=self.embedding_dimensions,
        )

    @property
    def cosmos_db_options(self) -> CosmosDBOptions:
        return CosmosDBOptions(
            endpoint=self.cosmos_endpoint,
            database=self.cosmos_database,
            history_container=self.cosmos_history_container,
            sync_state_container=self.cosmos_sync_state_container,
        )

    @property
    def service_bus_options(self) -> ServiceBusOptions:
        return ServiceBusOptions(
            fully_qualified_namespace=self.servicebus_namespace,
            queue_name=self.servicebus_queue_name,
        )

    @property
    def graph_options(self) -> GraphOptions:
        return GraphOptions(
            tenant_id=self.graph_tenant_id,
            client_id=self.graph_client_id,
        )

    @property
    def api_options(self) -> APIOptions:
        return APIOptions(
            require_jwt_validation=self.api_require_jwt_validation,
            obo_enabled=self.api_obo_enabled,
            obo_graph_scope=self.api_obo_graph_scope,
            auth_audience=self.api_auth_audience,
            allowed_app_client_ids=self.api_allowed_app_client_ids,
        )

    @property
    def workflow_options(self) -> WorkflowOptions:
        return WorkflowOptions(
            enabled=self.agentic_enabled,
            max_retrieval_iterations=self.workflow_max_retrieval_iterations,
            chat_history_window=self.workflow_chat_history_window,
            enable_query_rewriting=self.workflow_enable_query_rewriting,
            enable_reflection=self.workflow_enable_reflection,
            hyde_temperature=self.workflow_hyde_temperature,
            hyde_max_tokens=self.workflow_hyde_max_tokens,
            answer_temperature=self.workflow_answer_temperature,
            answer_max_tokens=self.workflow_answer_max_tokens,
            search_top_k=self.workflow_search_top_k,
            reflection_high_validity_threshold=self.reflection_high_validity_threshold,
            reflection_moderate_validity_threshold=self.reflection_moderate_validity_threshold,
            reflection_moderate_validity_min_count=self.reflection_moderate_validity_min_count,
        )

    @property
    def pii_detection_options(self) -> PIIDetectionOptions:
        return PIIDetectionOptions(
            enabled=self.pii_enabled,
            endpoint=self.pii_endpoint,
            mode=self.pii_mode,
            block_on_detection=self.pii_block_on_detection,
            redact_responses=self.pii_redact_responses,
            language=self.pii_language,
            min_confidence=self.pii_min_confidence,
        )

    @property
    def foundry_agent_options(self) -> FoundryAgentOptions:
        return FoundryAgentOptions(
            enabled=self.foundry_enabled,
            project_endpoint=self.foundry_project_endpoint,
            agent_id=self.foundry_agent_id,
            kb_connection_name=self.foundry_kb_connection_name,
        )

    @property
    def app_configuration_options(self) -> AppConfigurationOptions:
        return AppConfigurationOptions(
            enabled=bool(self.app_config_endpoint),
            endpoint=self.app_config_endpoint,
            key_filter=self.app_config_key_filter,
            label_filter=self.app_config_label_filter,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
