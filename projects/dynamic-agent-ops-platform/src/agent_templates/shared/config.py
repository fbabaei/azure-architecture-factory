"""Shared configuration for agent templates."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    agent_type: str = "unknown"
    agent_framework_enabled: bool = field(
        default_factory=lambda: os.getenv("AGENT_FRAMEWORK_ENABLED", "0") == "1"
    )
    foundry_project_endpoint: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    )
    foundry_model_deployment: str = field(
        default_factory=lambda: os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4o")
    )
    applicationinsights_connection_string: str = field(
        default_factory=lambda: os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    )
    cosmos_endpoint: str = field(
        default_factory=lambda: os.getenv("COSMOS_ENDPOINT", "")
    )

    @property
    def foundry_runtime_enabled(self) -> bool:
        return (
            self.agent_framework_enabled
            and bool(self.foundry_project_endpoint)
            and bool(self.foundry_model_deployment)
        )
