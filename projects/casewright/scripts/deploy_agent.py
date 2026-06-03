#!/usr/bin/env python3
"""Provision the Foundry IQ knowledge base and (re)create the hosted case-knowledge agent.

This is casewright's code-first counterpart of the source ``deploy_agent.py``. It is
synchronous, uses ``httpx`` (no ``requests`` dependency), and builds the hosted agent in
code (casewright has no agent YAML / AgentManager).

Flow (``deploy``):
  1. Provision the knowledge source + knowledge base on Azure AI Search
     (:class:`casewright.ingestion.knowledge_base.KnowledgeBaseService`).
  2. Create / update a Foundry RemoteTool project connection that targets the KB MCP
     endpoint (ARM REST, ProjectManagedIdentity auth).
  3. Create the hosted Foundry agent with an ``mcp`` tool (``knowledge_base_retrieve``)
     bound to that connection, and print its id for ``FOUNDRY_AGENT_ID``.

Usage:
    python scripts/deploy_agent.py deploy [--skip-knowledge-base] [--knowledge-base-only]
    python scripts/deploy_agent.py delete --agent-id <id> [--delete-knowledge-base]

Requires: Search Service Contributor on the search service, and the project's caller able to
write connections + agents. Auth is via ``DefaultAzureCredential``.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Make the src-layout package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from casewright.agents.prompts import SYSTEM_PROMPT  # noqa: E402
from casewright.core.clients import get_credential  # noqa: E402
from casewright.core.settings import get_settings  # noqa: E402
from casewright.ingestion.knowledge_base import KnowledgeBaseService  # noqa: E402

AGENT_NAME = "case-knowledge-agent"
AGENT_DESCRIPTION = "Answers questions grounded in synced case documents via Foundry IQ retrieval."
MCP_SERVER_LABEL = "knowledge-base"
_ARM_CONNECTIONS_API_VERSION = "2025-10-01-preview"
_MANAGEMENT_SCOPE = "https://management.azure.com/.default"

logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _provision_knowledge_base() -> str:
    """Provision the knowledge source + knowledge base. Returns the KB name."""
    settings = get_settings()
    if not settings.search_endpoint:
        raise RuntimeError("SEARCHSERVICE_ENDPOINT is required to provision the knowledge base")
    kb = settings.knowledge_base_options
    logger.info(
        "Provisioning knowledge base '%s' on %s (api-version=%s)",
        kb.name,
        settings.search_endpoint,
        settings.search_kb_api_version,
    )
    svc = KnowledgeBaseService(
        search_endpoint=settings.search_endpoint, api_version=settings.search_kb_api_version
    )
    try:
        svc.create_or_update_knowledge_base(kb)
    finally:
        svc.close()
    return kb.name


def _resolve_project_resource_id(explicit: str, endpoint: str) -> str:
    """Return the ARM resource id of the Foundry project.

    Priority: explicit value -> constructed from AZURE_SUBSCRIPTION_ID + AZURE_RESOURCE_GROUP
    and the account/project parsed from the Foundry endpoint URL.
    """
    if explicit:
        return explicit if explicit.startswith("/") else f"/{explicit}"

    parsed = urlparse(endpoint)
    host = parsed.netloc or ""
    account = host.split(".", 1)[0] if host else ""
    path_parts = [p for p in parsed.path.split("/") if p]
    project = ""
    if "projects" in path_parts:
        idx = path_parts.index("projects")
        if idx + 1 < len(path_parts):
            project = path_parts[idx + 1]

    if not account or not project:
        raise RuntimeError(
            "Cannot parse account/project from Foundry endpoint; set FOUNDRY_PROJECT_RESOURCE_ID."
        )

    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
    resource_group = os.environ.get("AZURE_RESOURCE_GROUP", "")
    if not subscription_id or not resource_group:
        raise RuntimeError(
            "Cannot derive Foundry project resource id; set FOUNDRY_PROJECT_RESOURCE_ID "
            "or AZURE_SUBSCRIPTION_ID + AZURE_RESOURCE_GROUP."
        )

    return (
        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.CognitiveServices/accounts/{account}/projects/{project}"
    )


def _ensure_mcp_kb_connection(
    project_resource_id: str, connection_name: str, mcp_endpoint: str
) -> None:
    """Create/update a Foundry RemoteTool connection targeting the KB MCP endpoint (ARM REST)."""
    token = get_credential().get_token(_MANAGEMENT_SCOPE)
    headers = {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}
    url = (
        f"https://management.azure.com{project_resource_id}"
        f"/connections/{connection_name}?api-version={_ARM_CONNECTIONS_API_VERSION}"
    )
    body = {
        "name": connection_name,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": mcp_endpoint,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        },
    }
    logger.info("Provisioning RemoteTool connection '%s' -> %s", connection_name, mcp_endpoint)
    resp = httpx.put(url, headers=headers, json=body, timeout=60.0)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Failed to create/update connection '{connection_name}': {resp.status_code} {resp.text}"
        )
    logger.info("Connection '%s' created or updated.", connection_name)


def _create_agent(connection_name: str, mcp_endpoint: str) -> str:
    """Create the hosted agent with the KB MCP tool. Returns the agent id."""
    from azure.ai.projects import AIProjectClient

    settings = get_settings()
    client = AIProjectClient(
        endpoint=settings.foundry_project_endpoint, credential=get_credential()
    )
    tools = [
        {
            "type": "mcp",
            "server_label": MCP_SERVER_LABEL,
            "server_url": mcp_endpoint,
            "project_connection_id": connection_name,
        }
    ]
    logger.info("Creating hosted agent '%s' (model=%s)", AGENT_NAME, settings.chat_deployment)
    agent = client.agents.create_agent(
        model=settings.chat_deployment,
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        instructions=SYSTEM_PROMPT,
        tools=tools,
    )
    return str(getattr(agent, "id", ""))


def _deploy(skip_kb: bool, kb_only: bool, project_resource_id: str) -> None:
    settings = get_settings()
    kb_name = settings.kb_name
    if not skip_kb:
        kb_name = _provision_knowledge_base()

    if kb_only:
        print(json.dumps({"success": True, "knowledgeBaseName": kb_name}))
        return

    if not settings.foundry_project_endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is required to register the hosted agent")

    mcp_endpoint = settings.kb_mcp_endpoint
    resolved = _resolve_project_resource_id(
        project_resource_id or os.environ.get("FOUNDRY_PROJECT_RESOURCE_ID", ""),
        settings.foundry_project_endpoint,
    )
    _ensure_mcp_kb_connection(resolved, settings.foundry_kb_connection_name, mcp_endpoint)
    agent_id = _create_agent(settings.foundry_kb_connection_name, mcp_endpoint)

    logger.info("Agent created: %s", agent_id)
    logger.info("Set FOUNDRY_AGENT_ID=%s to route runtime traffic through Foundry.", agent_id)
    print(json.dumps({"success": True, "agentId": agent_id, "knowledgeBaseName": kb_name}))


def _delete(agent_id: str, delete_kb: bool) -> None:
    settings = get_settings()
    if agent_id:
        from azure.ai.projects import AIProjectClient

        client = AIProjectClient(
            endpoint=settings.foundry_project_endpoint, credential=get_credential()
        )
        client.agents.delete_agent(agent_id)
        logger.info("Deleted agent: %s", agent_id)

    if not delete_kb:
        return
    if not settings.search_endpoint:
        logger.warning("SEARCHSERVICE_ENDPOINT not configured; skipping KB teardown")
        return
    kb = settings.knowledge_base_options
    svc = KnowledgeBaseService(
        search_endpoint=settings.search_endpoint, api_version=settings.search_kb_api_version
    )
    try:
        svc.delete_knowledge_base(kb.name)
        for source in kb.knowledge_sources:
            svc.delete_knowledge_source(source.name)
    finally:
        svc.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision the Foundry IQ KB + hosted agent")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    deploy_p = sub.add_parser("deploy", help="Provision KB + create hosted agent")
    deploy_p.add_argument("--skip-knowledge-base", action="store_true")
    deploy_p.add_argument("--knowledge-base-only", action="store_true")
    deploy_p.add_argument("--project-resource-id", default="")

    delete_p = sub.add_parser("delete", help="Delete the hosted agent and optionally the KB")
    delete_p.add_argument("--agent-id", default="")
    delete_p.add_argument("--delete-knowledge-base", action="store_true")

    args = parser.parse_args()
    _configure_logging(args.verbose)

    if args.command == "deploy":
        _deploy(args.skip_knowledge_base, args.knowledge_base_only, args.project_resource_id)
    elif args.command == "delete":
        _delete(args.agent_id, args.delete_knowledge_base)


if __name__ == "__main__":
    main()
