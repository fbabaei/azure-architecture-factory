"""Configuration and settings for the meta-orchestrator service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # --- Azure AI Foundry / Agent Framework ---------------------------------
    agent_framework_enabled: bool = field(
        default_factory=lambda: os.getenv("AGENT_FRAMEWORK_ENABLED", "0") == "1"
    )
    foundry_project_endpoint: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    )
    foundry_model_deployment: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    )

    # --- Cosmos DB (agent registry + session state) -------------------------
    cosmos_endpoint: str = field(
        default_factory=lambda: os.getenv("COSMOS_ENDPOINT", "")
    )
    cosmos_database: str = field(
        default_factory=lambda: os.getenv("COSMOS_DATABASE", "daop")
    )

    # --- Azure Service Bus ---------------------------------------------------
    servicebus_namespace: str = field(
        default_factory=lambda: os.getenv("SERVICEBUS_NAMESPACE", "")
    )
    servicebus_tasks_queue: str = field(
        default_factory=lambda: os.getenv("SERVICEBUS_TASKS_QUEUE", "daop-tasks")
    )
    servicebus_results_queue: str = field(
        default_factory=lambda: os.getenv("SERVICEBUS_RESULTS_QUEUE", "daop-results")
    )
    servicebus_hitl_queue: str = field(
        default_factory=lambda: os.getenv("SERVICEBUS_HITL_QUEUE", "daop-hitl")
    )

    # --- Agent Factory service ----------------------------------------------
    agent_factory_url: str = field(
        default_factory=lambda: os.getenv("AGENT_FACTORY_URL", "http://localhost:8081")
    )

    # --- Agent Registry service ----------------------------------------------
    agent_registry_url: str = field(
        default_factory=lambda: os.getenv(
            "AGENT_REGISTRY_URL", "http://localhost:8082"
        )
    )

    # --- Application Insights -----------------------------------------------
    applicationinsights_connection_string: str = field(
        default_factory=lambda: os.getenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
        )
    )

    # --- Agent TTL (seconds idle before suspension) -------------------------
    agent_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("AGENT_TTL_SECONDS", "3600"))
    )

    # --- HITL ---------------------------------------------------------------
    hitl_enabled: bool = field(
        default_factory=lambda: os.getenv("HITL_ENABLED", "1") == "1"
    )

    @property
    def foundry_runtime_enabled(self) -> bool:
        """True only when all three Foundry flags are populated."""
        return (
            self.agent_framework_enabled
            and bool(self.foundry_project_endpoint)
            and bool(self.foundry_model_deployment)
        )
