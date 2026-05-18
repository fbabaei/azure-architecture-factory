"""Configuration for the agent registry service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    cosmos_endpoint: str = field(default_factory=lambda: os.getenv("COSMOS_ENDPOINT", ""))
    cosmos_database: str = field(default_factory=lambda: os.getenv("COSMOS_DATABASE", "daop"))
    applicationinsights_connection_string: str = field(
        default_factory=lambda: os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    )
