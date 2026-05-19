"""Settings for the factory runtime package.

Mirrors the ``Settings`` / ``foundry_runtime_enabled`` convention from
``factory-templates/agent-framework/`` so the factory's own classifier
reads the same env flags an adopting project would.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FactorySettings:
    """Env-driven configuration for the factory classifier runtime.

    Read once at runtime; pass explicitly to tests via kwargs so the
    frozen dataclass defaults don't capture env state at import time.
    """

    agent_framework_enabled: bool = False
    foundry_project_endpoint: str | None = None
    foundry_model_deployment: str | None = None

    @classmethod
    def from_env(cls) -> "FactorySettings":
        return cls(
            agent_framework_enabled=os.getenv("FACTORY_AGENT_FRAMEWORK_ENABLED", "0") == "1",
            foundry_project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT") or None,
            foundry_model_deployment=os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME") or None,
        )

    @property
    def foundry_runtime_enabled(self) -> bool:
        """True only when the SDK runtime should be attempted.

        Mirrors the convention adopting projects use.
        """

        return bool(
            self.agent_framework_enabled
            and self.foundry_project_endpoint
            and self.foundry_model_deployment
        )
