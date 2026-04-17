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
    openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
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

    # Azure AI Search (optional for compliance knowledge grounding)
    ai_search_endpoint: str = os.getenv("AZURE_AI_SEARCH_ENDPOINT", "")
    ai_search_index_name: str = os.getenv(
        "AZURE_AI_SEARCH_INDEX_NAME", "compliance-knowledge-base"
    )
    ai_search_api_key: str = os.getenv("AZURE_AI_SEARCH_API_KEY", "")

    # Observability
    appinsights_connection_string: str = os.getenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
    )

    @property
    def azure_enabled(self) -> bool:
        """True when minimum Azure dependencies are configured."""
        return bool(self.openai_endpoint and self.blob_account_url)


def get_settings() -> Settings:
    return Settings()
