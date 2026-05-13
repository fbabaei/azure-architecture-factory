"""
Unit tests for the aca-express-deployer agent.

These are static-content validation tests — no Azure credentials or live CLI calls
are required. The tests verify:

1.  Agent file existence and correct frontmatter shape.
2.  All required frontmatter fields are present with expected values.
3.  Eligibility criteria are fully documented (all disqualifiers + both valid regions).
4.  Required CLI command patterns are present in the agent body.
5.  Expected output artifact paths are referenced.
6.  The fallback / `eligible: false` path is documented.
7.  The management portal URL is referenced.
8.  The project-orchestrator wires the agent into Phase 5 correctly (Path A / Path B).
9.  The squad routing table references aca-express-deployer.
10. The agents README tree contains the new agent entry.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO / ".github" / "agents"
AGENT_FILE = AGENTS_DIR / "aca-express-deployer.agent.md"
ORCHESTRATOR_FILE = AGENTS_DIR / "project-orchestrator.agent.md"
ROUTING_FILE = REPO / ".squad" / "routing.md"
README_FILE = AGENTS_DIR / "README.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML-like frontmatter between the first pair of '---' delimiters."""
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}
    end = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---"), None)
    if end is None:
        return {}
    fm: dict[str, str] = {}
    for ln in lines[1:end]:
        if ":" in ln:
            key, _, val = ln.partition(":")
            fm[key.strip()] = val.strip()
    return fm


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------


class TestAgentFileExists:
    def test_agent_file_present(self):
        assert AGENT_FILE.exists(), f"Agent file missing: {AGENT_FILE}"

    def test_agent_file_not_empty(self):
        assert AGENT_FILE.stat().st_size > 500, "Agent file appears to be empty or truncated"


# ---------------------------------------------------------------------------
# 2. Frontmatter fields
# ---------------------------------------------------------------------------


class TestFrontmatter:
    @pytest.fixture(scope="class")
    def fm(self) -> dict[str, str]:
        return _parse_frontmatter(_read(AGENT_FILE))

    def test_name_field(self, fm):
        assert fm.get("name") == "aca-express-deployer"

    def test_description_present(self, fm):
        desc = fm.get("description", "")
        assert len(desc) > 20, "description field is too short or missing"

    def test_description_mentions_express(self, fm):
        assert "Express" in fm.get("description", "") or "express" in fm.get("description", "")

    def test_tools_field_present(self, fm):
        assert "tools" in fm, "tools field missing from frontmatter"

    def test_tools_contains_execute(self, fm):
        assert "execute" in fm.get("tools", ""), "tools must include 'execute' for CLI commands"

    def test_user_invocable_is_true(self, fm):
        assert fm.get("user-invocable") == "true"

    def test_argument_hint_present(self, fm):
        assert "argument-hint" in fm, "argument-hint field missing from frontmatter"

    def test_argument_hint_mentions_image(self, fm):
        hint = fm.get("argument-hint", "")
        assert "image" in hint.lower(), "argument-hint should reference container image parameter"

    def test_foundry_capabilities_present(self, fm):
        assert "foundry_capabilities" in fm


# ---------------------------------------------------------------------------
# 3. Eligibility criteria
# ---------------------------------------------------------------------------


class TestEligibilityCriteria:
    @pytest.fixture(scope="class")
    def body(self) -> str:
        return _read(AGENT_FILE)

    # --- Supported regions ---
    def test_westcentralus_mentioned(self, body):
        assert "westcentralus" in body, "westcentralus region must be documented in eligibility section"

    def test_eastasia_mentioned(self, body):
        assert "eastasia" in body, "eastasia region must be documented in eligibility section"

    # --- Disqualifying conditions ---
    def test_gpu_disqualifier_documented(self, body):
        assert re.search(r"GPU", body, re.IGNORECASE), "GPU disqualifier must be documented"

    def test_vnet_disqualifier_documented(self, body):
        assert re.search(r"VNet|vnet|virtual.?network", body, re.IGNORECASE), "VNet disqualifier must be documented"

    def test_dapr_disqualifier_documented(self, body):
        assert "Dapr" in body or "dapr" in body, "Dapr disqualifier must be documented"

    def test_jobs_disqualifier_documented(self, body):
        assert re.search(r"jobs?|batch", body, re.IGNORECASE), "Jobs/batch disqualifier must be documented"

    def test_tcp_disqualifier_documented(self, body):
        assert "TCP" in body or "tcp" in body, "TCP disqualifier must be documented"

    def test_service_discovery_disqualifier_documented(self, body):
        assert re.search(r"service.?discovery|internal.?fqdn", body, re.IGNORECASE), \
            "Service-discovery disqualifier must be documented"

    # --- Eligibility section exists ---
    def test_eligibility_section_present(self, body):
        assert re.search(r"eligib", body, re.IGNORECASE), "Eligibility section missing from agent body"

    def test_eligible_false_return_documented(self, body):
        assert "eligible: false" in body, "Agent must document returning 'eligible: false' to the orchestrator"


# ---------------------------------------------------------------------------
# 4. CLI command patterns
# ---------------------------------------------------------------------------


class TestCliCommands:
    @pytest.fixture(scope="class")
    def body(self) -> str:
        return _read(AGENT_FILE)

    def test_az_containerapp_env_create(self, body):
        assert "az containerapp env create" in body

    def test_environment_mode_express_flag(self, body):
        assert "--environment-mode express" in body

    def test_az_containerapp_up(self, body):
        assert "az containerapp up" in body

    def test_az_containerapp_show_fqdn(self, body):
        assert "az containerapp show" in body
        assert "fqdn" in body.lower()

    def test_az_containerapp_logs(self, body):
        assert "az containerapp logs" in body

    def test_logs_destination_none(self, body):
        assert "--logs-destination none" in body

    def test_az_account_show_prerequisite(self, body):
        assert "az account show" in body

    def test_az_containerapp_update_for_redeploy(self, body):
        assert "az containerapp update" in body


# ---------------------------------------------------------------------------
# 5. Output artifacts
# ---------------------------------------------------------------------------


class TestOutputArtifacts:
    @pytest.fixture(scope="class")
    def body(self) -> str:
        return _read(AGENT_FILE)

    def test_deploy_express_sh_referenced(self, body):
        assert "deploy-express.sh" in body

    def test_deploy_express_ps1_referenced(self, body):
        assert "deploy-express.ps1" in body

    def test_phase5_deployment_log_referenced(self, body):
        assert "phase-5-deployment.log" in body

    def test_deploy_md_referenced(self, body):
        assert "DEPLOY.md" in body


# ---------------------------------------------------------------------------
# 6. Management portal URL
# ---------------------------------------------------------------------------


class TestPortalUrl:
    def test_containerapps_portal_url_present(self):
        body = _read(AGENT_FILE)
        assert "https://containerapps.azure.com/" in body, \
            "Management portal URL https://containerapps.azure.com/ must be referenced"


# ---------------------------------------------------------------------------
# 7. Feature gap table
# ---------------------------------------------------------------------------


class TestFeatureGapTable:
    @pytest.fixture(scope="class")
    def body(self) -> str:
        return _read(AGENT_FILE)

    def test_managed_identity_gap_documented(self, body):
        assert re.search(r"managed.?identity", body, re.IGNORECASE)

    def test_key_vault_gap_documented(self, body):
        assert re.search(r"key.?vault", body, re.IGNORECASE)

    def test_custom_domain_gap_documented(self, body):
        assert re.search(r"custom.?domain", body, re.IGNORECASE)

    def test_keda_gap_documented(self, body):
        assert re.search(r"KEDA|keda", body)

    def test_cors_gap_documented(self, body):
        assert re.search(r"CORS|cors", body, re.IGNORECASE)


# ---------------------------------------------------------------------------
# 8. Orchestrator wiring
# ---------------------------------------------------------------------------


class TestOrchestratorWiring:
    @pytest.fixture(scope="class")
    def orch(self) -> str:
        assert ORCHESTRATOR_FILE.exists(), f"Orchestrator file missing: {ORCHESTRATOR_FILE}"
        return _read(ORCHESTRATOR_FILE)

    def test_aca_express_deployer_in_agents_list(self, orch):
        """Frontmatter agents: array must contain aca-express-deployer."""
        fm = _parse_frontmatter(orch)
        agents_value = fm.get("agents", "")
        assert "aca-express-deployer" in agents_value, \
            "aca-express-deployer must appear in the orchestrator's agents: frontmatter list"

    def test_azure_project_deployer_still_in_agents_list(self, orch):
        """Original fallback agent must still be present."""
        fm = _parse_frontmatter(orch)
        assert "azure-project-deployer" in fm.get("agents", "")

    def test_phase5_path_a_present(self, orch):
        """Phase 5 must document the ACA Express path (Path A)."""
        assert "Path A" in orch or "aca-express-deployer" in orch

    def test_phase5_path_b_present(self, orch):
        """Phase 5 must document the standard Bicep path (Path B)."""
        assert "Path B" in orch or "azure-project-deployer" in orch

    def test_phase5_express_regions_mentioned(self, orch):
        """Phase 5 section must reference the two supported preview regions."""
        assert "westcentralus" in orch and "eastasia" in orch

    def test_phase5_fallback_documented(self, orch):
        """Orchestrator must document the fallback to azure-project-deployer."""
        assert "azure-project-deployer" in orch

    def test_phase5_eligible_false_handled(self, orch):
        """Orchestrator must handle the eligible: false return value."""
        assert "eligible: false" in orch


# ---------------------------------------------------------------------------
# 9. Squad routing
# ---------------------------------------------------------------------------


class TestSquadRouting:
    @pytest.fixture(scope="class")
    def routing(self) -> str:
        assert ROUTING_FILE.exists(), f"routing.md missing: {ROUTING_FILE}"
        return _read(ROUTING_FILE)

    def test_aca_express_row_present(self, routing):
        assert "aca-express-deployer" in routing, \
            "aca-express-deployer must appear in .squad/routing.md routing table"

    def test_fallback_agent_mentioned(self, routing):
        assert "azure-project-deployer" in routing, \
            "azure-project-deployer must still appear in routing.md as a fallback"

    def test_aca_express_row_describes_http(self, routing):
        assert re.search(r"HTTP|http", routing), \
            "Routing entry for ACA Express should note it is for HTTP workloads"


# ---------------------------------------------------------------------------
# 10. Agents README tree
# ---------------------------------------------------------------------------


class TestAgentsReadme:
    @pytest.fixture(scope="class")
    def readme(self) -> str:
        assert README_FILE.exists(), f"agents README missing: {README_FILE}"
        return _read(README_FILE)

    def test_aca_express_deployer_in_readme(self, readme):
        assert "aca-express-deployer" in readme, \
            "aca-express-deployer must appear in .github/agents/README.md"

    def test_readme_references_express_as_path_a(self, readme):
        """README should convey that Express is an alternative (Path A) to azure-project-deployer."""
        assert re.search(r"Phase 5.*(A|express)|aca-express", readme, re.IGNORECASE | re.DOTALL), \
            "README should document aca-express-deployer as the Phase 5 Express path"

    def test_azure_project_deployer_still_in_readme(self, readme):
        assert "azure-project-deployer" in readme, \
            "azure-project-deployer must remain in the README tree as the standard path"


# ---------------------------------------------------------------------------
# 11. No hard-coded secrets / subscription IDs
# ---------------------------------------------------------------------------


class TestSecurityConstraints:
    @pytest.fixture(scope="class")
    def body(self) -> str:
        return _read(AGENT_FILE)

    def test_no_hard_coded_subscription_id(self, body):
        """Agent must not contain a real Azure subscription GUID."""
        # Real subscription IDs are 36-char UUIDs — reject any that look like real values
        # but allow the generic placeholder patterns used in docs.
        real_guid = re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        )
        matches = real_guid.findall(body)
        assert not matches, f"Possible hard-coded GUID(s) found in agent file: {matches}"

    def test_no_connection_strings(self, body):
        assert "AccountKey=" not in body, "Connection string with AccountKey must not appear in agent file"
        assert "DefaultEndpointsProtocol=" not in body

    def test_constraint_no_hardcode_mentioned(self, body):
        """Agent instructions must explicitly forbid hard-coding credentials."""
        assert re.search(r"NEVER hard.?code|never.*secret|never.*key", body, re.IGNORECASE), \
            "Agent must include an explicit NEVER hard-code-secrets constraint"
