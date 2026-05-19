"""Configuration for the agent factory service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    agent_framework_enabled: bool = field(
        default_factory=lambda: os.getenv("AGENT_FRAMEWORK_ENABLED", "0") == "1"
    )
    foundry_project_endpoint: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    )
    foundry_model_deployment: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    )
    cosmos_endpoint: str = field(
        default_factory=lambda: os.getenv("COSMOS_ENDPOINT", "")
    )
    cosmos_database: str = field(
        default_factory=lambda: os.getenv("COSMOS_DATABASE", "daop")
    )
    servicebus_namespace: str = field(
        default_factory=lambda: os.getenv("SERVICEBUS_NAMESPACE", "")
    )
    servicebus_tasks_queue: str = field(
        default_factory=lambda: os.getenv("SERVICEBUS_TASKS_QUEUE", "daop-tasks")
    )
    agent_registry_url: str = field(
        default_factory=lambda: os.getenv("AGENT_REGISTRY_URL", "http://localhost:8082")
    )
    applicationinsights_connection_string: str = field(
        default_factory=lambda: os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    )

    @property
    def foundry_runtime_enabled(self) -> bool:
        return (
            self.agent_framework_enabled
            and bool(self.foundry_project_endpoint)
            and bool(self.foundry_model_deployment)
        )
