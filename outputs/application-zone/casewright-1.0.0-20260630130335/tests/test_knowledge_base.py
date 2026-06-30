"""Connectivity-free tests for the Foundry IQ knowledge-base wiring."""
from __future__ import annotations

import pytest


def _settings(**env: str):
    from casewright.core.settings import Settings

    return Settings(**env)


def test_kb_mcp_endpoint_built_from_search_endpoint():
    s = _settings(
        SEARCHSERVICE_ENDPOINT="https://example.search.windows.net/",
        SEARCH_KB_API_VERSION="2025-11-01-preview",
        SEARCH_KB_NAME="casewright-kb",
    )
    assert s.kb_mcp_endpoint == (
        "https://example.search.windows.net/knowledgebases/casewright-kb/mcp"
        "?api-version=2025-11-01-preview"
    )


def test_knowledge_base_options_falls_back_to_primary_settings():
    s = _settings(
        SEARCHSERVICE_ENDPOINT="https://example.search.windows.net",
        SEARCH_INDEX_NAME="casewright-index",
        SEARCH_SEMANTIC_CONFIGURATION="casewright-semantic",
        AZURE_OPENAI_ENDPOINT="https://aoai.openai.azure.com/",
        AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4o",
    )
    kb = s.knowledge_base_options
    assert kb.name == "casewright-kb"
    assert kb.aoai_endpoint == "https://aoai.openai.azure.com"
    assert kb.aoai_deployment_name == "gpt-4o"
    assert len(kb.knowledge_sources) == 1
    src = kb.knowledge_sources[0]
    assert src.name == "casewright-ks"
    assert src.index_name == "casewright-index"
    assert src.semantic_configuration_name == "casewright-semantic"


def test_foundry_enabled_requires_endpoint_and_agent_id():
    assert _settings().foundry_enabled is False
    assert (
        _settings(
            FOUNDRY_PROJECT_ENDPOINT="https://x.services.ai.azure.com/api/projects/p",
            FOUNDRY_AGENT_ID="asst_123",
        ).foundry_enabled
        is True
    )


def test_build_source_body_shape():
    from casewright.core.config_options import KnowledgeSourceOptions
    from casewright.ingestion.knowledge_base import KnowledgeBaseService

    svc = KnowledgeBaseService(
        "https://example.search.windows.net",
        credential=object(),  # not used by body builders
    )
    body = svc._build_source_body(
        KnowledgeSourceOptions(
            name="casewright-ks",
            index_name="casewright-index",
            description="desc",
            source_data_fields=["content", "title"],
            search_fields=["content"],
            semantic_configuration_name="casewright-semantic",
        )
    )
    assert body["name"] == "casewright-ks"
    assert body["kind"] == "searchIndex"
    params = body["searchIndexParameters"]
    assert params["searchIndexName"] == "casewright-index"
    assert params["sourceDataFields"] == [{"name": "content"}, {"name": "title"}]
    assert params["searchFields"] == [{"name": "content"}]
    assert params["semanticConfigurationName"] == "casewright-semantic"
    assert body["description"] == "desc"


def test_build_kb_body_promotes_reasoning_and_output_mode():
    from casewright.core.config_options import KnowledgeBaseOptions, KnowledgeSourceOptions
    from casewright.ingestion.knowledge_base import KnowledgeBaseService

    svc = KnowledgeBaseService("https://example.search.windows.net", credential=object())
    kb = KnowledgeBaseOptions(
        name="casewright-kb",
        description="kb desc",
        knowledge_sources=[KnowledgeSourceOptions(name="casewright-ks", index_name="casewright-index")],
        aoai_endpoint="https://aoai.openai.azure.com",
        aoai_deployment_name="gpt-4o",
        output_modality="extractiveData",
        retrieval_reasoning_effort="medium",
        retrieval_instructions="answer from docs",
    )
    body = svc._build_kb_body(kb)
    assert body["name"] == "casewright-kb"
    assert body["knowledgeSources"] == [{"name": "casewright-ks"}]
    assert body["outputMode"] == "extractiveData"
    assert body["retrievalReasoningEffort"] == {"kind": "medium"}
    assert body["retrievalInstructions"] == "answer from docs"
    model = body["models"][0]
    assert model["kind"] == "azureOpenAI"
    assert model["azureOpenAIParameters"]["resourceUri"] == "https://aoai.openai.azure.com"
    assert model["azureOpenAIParameters"]["deploymentId"] == "gpt-4o"


def test_url_includes_api_version():
    from casewright.ingestion.knowledge_base import KnowledgeBaseService

    svc = KnowledgeBaseService(
        "https://example.search.windows.net",
        credential=object(),
        api_version="2025-11-01-preview",
    )
    assert svc._url("knowledgebases('casewright-kb')") == (
        "https://example.search.windows.net/knowledgebases('casewright-kb')"
        "?api-version=2025-11-01-preview"
    )


def test_create_or_update_kb_requires_aoai_settings():
    from casewright.core.config_options import KnowledgeBaseOptions, KnowledgeSourceOptions
    from casewright.ingestion.knowledge_base import KnowledgeBaseService

    svc = KnowledgeBaseService("https://example.search.windows.net", credential=object())
    kb = KnowledgeBaseOptions(
        name="casewright-kb",
        knowledge_sources=[KnowledgeSourceOptions(name="casewright-ks", index_name="casewright-index")],
    )
    with pytest.raises(ValueError):
        svc.create_or_update_knowledge_base(kb)
