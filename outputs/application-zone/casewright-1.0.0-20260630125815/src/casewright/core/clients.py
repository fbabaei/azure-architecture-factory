"""Lazily-constructed Azure SDK clients, all wired with DefaultAzureCredential.

No account keys anywhere — every client authenticates with managed identity (or developer
identity locally via the Azure CLI / VS Code login that DefaultAzureCredential resolves).
"""
from __future__ import annotations

from functools import lru_cache

from azure.identity import DefaultAzureCredential

from casewright.core.settings import get_settings


@lru_cache(maxsize=1)
def get_credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


@lru_cache(maxsize=1)
def get_search_index_client():
    from azure.search.documents.indexes import SearchIndexClient

    s = get_settings()
    return SearchIndexClient(endpoint=s.search_endpoint, credential=get_credential())


def get_search_client(index_name: str | None = None):
    from azure.search.documents import SearchClient

    s = get_settings()
    return SearchClient(
        endpoint=s.search_endpoint,
        index_name=index_name or s.search_index_name,
        credential=get_credential(),
    )


@lru_cache(maxsize=1)
def get_search_indexer_client():
    from azure.search.documents.indexes import SearchIndexerClient

    s = get_settings()
    return SearchIndexerClient(endpoint=s.search_endpoint, credential=get_credential())


@lru_cache(maxsize=1)
def get_blob_service_client():
    from azure.storage.blob import BlobServiceClient

    s = get_settings()
    return BlobServiceClient(account_url=s.blob_account_url, credential=get_credential())


@lru_cache(maxsize=1)
def get_cosmos_client():
    from azure.cosmos import CosmosClient

    s = get_settings()
    return CosmosClient(url=s.cosmos_endpoint, credential=get_credential())


@lru_cache(maxsize=1)
def get_openai_client():
    from azure.identity import get_bearer_token_provider
    from openai import AzureOpenAI

    s = get_settings()
    token_provider = get_bearer_token_provider(
        get_credential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=s.openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )
