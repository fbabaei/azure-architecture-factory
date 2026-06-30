"""Azure AI Search Knowledge Source + Knowledge Base provisioning.

Uses the Azure AI Search REST preview API (``2025-11-01-preview``) which exposes
``/knowledgeSources/{name}`` and ``/knowledgebases('{name}')`` resources and
promotes ``retrievalReasoningEffort`` and ``outputMode`` to top-level properties
on the knowledge base. Each provisioned knowledge base also exposes an MCP
endpoint (``/knowledgebases/{name}/mcp``) with a ``knowledge_base_retrieve`` tool
that the hosted Foundry agent calls for agentic retrieval.

This is the synchronous, casewright-idiomatic counterpart of the source
``KnowledgeBaseService`` (it uses ``httpx.Client`` + the shared sync
``DefaultAzureCredential`` rather than the async stack).

RBAC requirements:
    * Caller running provisioning needs ``Search Service Contributor`` on the
      search service (PUT/DELETE knowledgeSources + knowledgebases).
    * The search service managed identity needs ``Cognitive Services OpenAI User``
      on the Azure OpenAI account so the knowledge base can call the model.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from azure.core.credentials import TokenCredential

from casewright.core.clients import get_credential
from casewright.core.config_options import KnowledgeBaseOptions, KnowledgeSourceOptions

_SEARCH_SCOPE = "https://search.azure.com/.default"
_DEFAULT_API_VERSION = "2025-11-01-preview"

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """REST client for provisioning Search knowledge sources + knowledge bases."""

    def __init__(
        self,
        search_endpoint: str,
        credential: TokenCredential | None = None,
        api_version: str = _DEFAULT_API_VERSION,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not search_endpoint:
            raise ValueError("search_endpoint is required")
        self._endpoint = search_endpoint.rstrip("/")
        self._credential = credential or get_credential()
        self._api_version = api_version
        self._http = http_client or httpx.Client(timeout=httpx.Timeout(60.0))
        self._owns_http = http_client is None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "KnowledgeBaseService":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        token = self._credential.get_token(_SEARCH_SCOPE)
        return {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._endpoint}/{path}?api-version={self._api_version}"

    def create_or_update_knowledge_source(self, source: KnowledgeSourceOptions) -> None:
        body = self._build_source_body(source)
        url = self._url(f"knowledgeSources/{source.name}")
        resp = self._http.put(url, headers=self._headers(), json=body)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Failed to PUT knowledge source '{source.name}': {resp.status_code} {resp.text}"
            )
        logger.info("Knowledge source '%s' upserted (HTTP %s)", source.name, resp.status_code)

    def create_or_update_knowledge_base(self, kb: KnowledgeBaseOptions) -> None:
        if not kb.knowledge_sources:
            raise ValueError(f"Knowledge base '{kb.name}' has no knowledge_sources")
        if not kb.aoai_endpoint or not kb.aoai_deployment_name:
            raise ValueError(
                f"Knowledge base '{kb.name}' requires aoai_endpoint and aoai_deployment_name"
            )

        # Upsert each source first so the KB binding is valid.
        for source in kb.knowledge_sources:
            self.create_or_update_knowledge_source(source)

        body = self._build_kb_body(kb)
        url = self._url(f"knowledgebases('{kb.name}')")
        resp = self._http.put(url, headers=self._headers(), json=body)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Failed to PUT knowledge base '{kb.name}': {resp.status_code} {resp.text}"
            )
        logger.info("Knowledge base '%s' upserted (HTTP %s)", kb.name, resp.status_code)

    def delete_knowledge_base(self, name: str) -> None:
        url = self._url(f"knowledgebases('{name}')")
        resp = self._http.delete(url, headers=self._headers())
        if resp.status_code in (200, 204, 404):
            logger.info("Knowledge base '%s' delete -> HTTP %s", name, resp.status_code)
            return
        raise RuntimeError(f"Failed to DELETE knowledge base '{name}': {resp.status_code} {resp.text}")

    def delete_knowledge_source(self, name: str) -> None:
        url = self._url(f"knowledgeSources/{name}")
        resp = self._http.delete(url, headers=self._headers())
        if resp.status_code in (200, 204, 404):
            logger.info("Knowledge source '%s' delete -> HTTP %s", name, resp.status_code)
            return
        raise RuntimeError(f"Failed to DELETE knowledge source '{name}': {resp.status_code} {resp.text}")

    def get_knowledge_base(self, name: str) -> dict[str, Any] | None:
        url = self._url(f"knowledgebases('{name}')")
        resp = self._http.get(url, headers=self._headers())
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise RuntimeError(f"Failed to GET knowledge base '{name}': {resp.status_code} {resp.text}")
        return resp.json()

    # ------------------------------------------------------------------
    # Body builders
    # ------------------------------------------------------------------

    def _build_source_body(self, source: KnowledgeSourceOptions) -> dict[str, Any]:
        params: dict[str, Any] = {"searchIndexName": source.index_name}
        if source.source_data_fields:
            params["sourceDataFields"] = [{"name": f} for f in source.source_data_fields]
        if source.search_fields:
            params["searchFields"] = [{"name": f} for f in source.search_fields]
        if source.semantic_configuration_name:
            params["semanticConfigurationName"] = source.semantic_configuration_name
        body: dict[str, Any] = {
            "name": source.name,
            "kind": source.kind,
            "searchIndexParameters": params,
        }
        if source.description:
            body["description"] = source.description
        return body

    def _build_kb_body(self, kb: KnowledgeBaseOptions) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": kb.name,
            "knowledgeSources": [{"name": s.name} for s in kb.knowledge_sources],
            "models": [
                {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": kb.aoai_endpoint,
                        "deploymentId": kb.aoai_deployment_name,
                        "modelName": kb.aoai_deployment_name,
                        # authIdentity omitted -> Search service system-assigned identity
                    },
                }
            ],
            "retrievalReasoningEffort": {"kind": kb.retrieval_reasoning_effort},
            "outputMode": kb.output_modality,
        }
        if kb.description:
            body["description"] = kb.description
        if kb.retrieval_instructions:
            body["retrievalInstructions"] = kb.retrieval_instructions
        return body
