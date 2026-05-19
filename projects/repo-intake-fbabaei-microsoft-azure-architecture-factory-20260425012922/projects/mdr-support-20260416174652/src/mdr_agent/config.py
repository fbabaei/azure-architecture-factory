"""Environment-driven configuration for the MDR agent."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables.

    All Azure-hosted dependencies are optional; when unset, the service
    falls back to in-memory stubs so the agent can run locally for
    development and tests.
    """

    # Azure OpenAI
    openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
    openai_embeddings_deployment: str = os.getenv(
        "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "text-embedding-3-small"
    )
    openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

    # Azure AI Document Intelligence
    doc_intel_endpoint: str = os.getenv("AZURE_DOC_INTEL_ENDPOINT", "")

    # Azure Blob Storage (uploaded source documents)
    blob_account_url: str = os.getenv("AZURE_BLOB_ACCOUNT_URL", "")
    blob_container: str = os.getenv("AZURE_BLOB_CONTAINER", "mdr-documents")

    # Azure Cosmos DB (arrangement drafts + chat sessions)
    cosmos_endpoint: str = os.getenv("AZURE_COSMOS_ENDPOINT", "")
    cosmos_database: str = os.getenv("AZURE_COSMOS_DATABASE", "mdr")
    cosmos_arrangements_container: str = os.getenv(
        "AZURE_COSMOS_ARRANGEMENTS_CONTAINER", "arrangements"
    )
    cosmos_sessions_container: str = os.getenv(
        "AZURE_COSMOS_SESSIONS_CONTAINER", "sessions"
    )
    cosmos_case_drafts_container: str = os.getenv(
        "AZURE_COSMOS_CASE_DRAFTS_CONTAINER", "case-drafts"
    )
    cosmos_audit_container: str = os.getenv(
        "AZURE_COSMOS_AUDIT_CONTAINER", "audit-log"
    )

    # Azure AI Search (optional for compliance knowledge grounding)
    ai_search_endpoint: str = os.getenv("AZURE_AI_SEARCH_ENDPOINT", "")
    ai_search_index_name: str = os.getenv(
        "AZURE_AI_SEARCH_INDEX_NAME", "compliance-knowledge-base"
    )
    ai_search_vector_field: str = os.getenv(
        "AZURE_AI_SEARCH_VECTOR_FIELD", "contentVector"
    )
    ai_search_semantic_configuration: str = os.getenv(
        "AZURE_AI_SEARCH_SEMANTIC_CONFIGURATION", "default"
    )
    ai_search_api_key: str = os.getenv("AZURE_AI_SEARCH_API_KEY", "")

    # Observability
    appinsights_connection_string: str = os.getenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
    )

    # Microsoft Agent Framework (Foundry) runtime - optional.
    # When enabled, the chat and extraction agents are driven by
    # ``agent_framework`` SDK ``Agent`` instances backed by
    # ``FoundryChatClient``. Falls back to the deterministic local
    # runtime when disabled or when the SDK is not installed.
    foundry_project_endpoint: str = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    foundry_model_deployment: str = os.getenv(
        "FOUNDRY_MODEL_DEPLOYMENT_NAME", ""
    )
    agent_framework_enabled: bool = os.getenv(
        "AGENT_FRAMEWORK_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

    @property
    def azure_enabled(self) -> bool:
        """True when minimum Azure dependencies are configured."""
        return bool(self.openai_endpoint and self.blob_account_url)

    @property
    def foundry_runtime_enabled(self) -> bool:
        """True when the Agent Framework SDK runtime should be used."""
        return bool(
            self.agent_framework_enabled
            and self.foundry_project_endpoint
            and self.foundry_model_deployment
        )


def get_settings() -> Settings:
    return Settings()
