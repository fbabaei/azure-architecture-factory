"""Registry service — CRUD operations on Cosmos DB with in-memory fallback."""
from __future__ import annotations

import logging
from typing import List, Optional

from agent_registry.config import Settings
from agent_registry.models import AgentSession, AgentTemplate

logger = logging.getLogger(__name__)

# In-memory fallback stores (seeded with default templates)
_TEMPLATES: dict[str, dict] = {}
_SESSIONS: dict[str, dict] = {}


def _seed_default_templates() -> None:
    defaults = [
        AgentTemplate(
            name="Architect Agent v1",
            agent_type="architect",
            description="Designs Azure architectures, generates IaC, calls AAF for diagram generation.",
            capabilities=["architecture_design", "iac_generation", "diagram_creation", "aaf_integration"],
            required_tools=["aaf_tool", "bicep_generator", "drawio_mcp"],
            system_prompt_template=(
                "You are an expert Azure solution architect. Given a project goal, "
                "design a complete Azure architecture, generate Bicep IaC, and produce "
                "an architecture diagram using the AAF tool. Always follow Microsoft WAF principles."
            ),
        ),
        AgentTemplate(
            name="Developer Agent v1",
            agent_type="developer",
            description="Generates, reviews, and refactors Python and .NET service code.",
            capabilities=["code_generation", "code_review", "test_writing", "refactoring"],
            required_tools=["github_api", "file_tools", "copilot_api"],
            system_prompt_template=(
                "You are an expert software engineer specializing in Python and .NET. "
                "Generate clean, tested, production-ready code following the project's conventions."
            ),
        ),
        AgentTemplate(
            name="Ops Agent v1",
            agent_type="ops",
            description="Handles deployments, monitoring, and incident triage.",
            capabilities=["deployment", "monitoring", "incident_triage", "cost_optimization"],
            required_tools=["azure_cli_tools", "container_apps_api", "app_insights_api"],
            system_prompt_template=(
                "You are a DevOps engineer with deep Azure expertise. "
                "Deploy, monitor, and troubleshoot Azure workloads. "
                "Always prefer zero-downtime deployment strategies."
            ),
        ),
        AgentTemplate(
            name="Analyst Agent v1",
            agent_type="analyst",
            description="Analyzes requirements, estimates costs, and produces traceability matrices.",
            capabilities=["requirements_analysis", "cost_estimation", "traceability", "documentation"],
            required_tools=["azure_cost_api", "doc_tools", "aaf_intake"],
            system_prompt_template=(
                "You are a business and technical analyst. "
                "Decompose goals into requirements, estimate Azure costs, and produce traceability documents."
            ),
        ),
        AgentTemplate(
            name="Security Agent v1",
            agent_type="security",
            description="Performs CVE scanning, RBAC audits, and compliance checks.",
            capabilities=["cve_scanning", "rbac_audit", "compliance_check", "secret_detection"],
            required_tools=["azqr_tool", "key_vault_api", "defender_api"],
            system_prompt_template=(
                "You are a cloud security engineer. "
                "Audit Azure resources for security misconfigurations, scan for CVEs, "
                "and ensure compliance with organizational policies."
            ),
        ),
    ]
    for t in defaults:
        _TEMPLATES[t.template_id] = t.model_dump(mode="json")


_seed_default_templates()


class RegistryService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._templates_container = None
        self._sessions_container = None
        if settings.cosmos_endpoint:
            self._templates_container, self._sessions_container = self._init_cosmos(settings)

    def _init_cosmos(self, settings: Settings):
        try:
            from azure.cosmos.aio import CosmosClient  # type: ignore[import]
            from azure.identity.aio import DefaultAzureCredential  # type: ignore[import]

            client = CosmosClient(settings.cosmos_endpoint, credential=DefaultAzureCredential())
            db = client.get_database_client(settings.cosmos_database)
            return (
                db.get_container_client("agent_templates"),
                db.get_container_client("agent_sessions"),
            )
        except Exception as exc:
            logger.warning("Cosmos DB init failed (%s); using in-memory store.", exc)
            return None, None

    # --- Templates ----------------------------------------------------------

    async def list_templates(
        self, agent_type: Optional[str] = None
    ) -> List[AgentTemplate]:
        if self._templates_container is not None:
            try:
                query = "SELECT * FROM c WHERE c.active = true"
                params = []
                if agent_type:
                    query += " AND c.agent_type = @agent_type"
                    params.append({"name": "@agent_type", "value": agent_type})
                items = [
                    item
                    async for item in self._templates_container.query_items(
                        query=query, parameters=params
                    )
                ]
                return [AgentTemplate(**i) for i in items]
            except Exception as exc:
                logger.warning("Cosmos template list failed: %s", exc)
        items = list(_TEMPLATES.values())
        if agent_type:
            items = [i for i in items if i.get("agent_type") == agent_type]
        return [AgentTemplate(**i) for i in items]

    async def get_template(self, template_id: str) -> Optional[AgentTemplate]:
        if self._templates_container is not None:
            try:
                doc = await self._templates_container.read_item(template_id, partition_key=template_id)
                return AgentTemplate(**doc)
            except Exception:
                pass
        doc = _TEMPLATES.get(template_id)
        return AgentTemplate(**doc) if doc else None

    async def save_template(self, template: AgentTemplate) -> None:
        doc = template.model_dump(mode="json")
        doc["id"] = template.template_id
        if self._templates_container is not None:
            try:
                await self._templates_container.upsert_item(doc)
                return
            except Exception as exc:
                logger.warning("Cosmos template upsert failed: %s", exc)
        _TEMPLATES[template.template_id] = doc

    # --- Sessions -----------------------------------------------------------

    async def upsert_session(self, session: AgentSession) -> None:
        doc = session.model_dump(mode="json")
        doc["id"] = session.session_id
        if self._sessions_container is not None:
            try:
                await self._sessions_container.upsert_item(doc)
                return
            except Exception as exc:
                logger.warning("Cosmos session upsert failed: %s", exc)
        _SESSIONS[session.session_id] = doc

    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        if self._sessions_container is not None:
            try:
                doc = await self._sessions_container.read_item(session_id, partition_key=session_id)
                return AgentSession(**doc)
            except Exception:
                pass
        doc = _SESSIONS.get(session_id)
        return AgentSession(**doc) if doc else None
