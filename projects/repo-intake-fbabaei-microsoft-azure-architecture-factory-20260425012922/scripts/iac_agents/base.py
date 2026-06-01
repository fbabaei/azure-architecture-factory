"""Shared contract for Infrastructure-as-Code specialist agents.

An IaC agent owns emission of infrastructure templates for one toolchain
(Bicep, Terraform, Pulumi, ARM, etc.).

Adding a new IaC tool means:
  1. Create `scripts/iac_agents/<tool>_agent.py` exporting an `AGENT` instance.
  2. Register it in `scripts/iac_agents/__init__.py`.
No other runner changes required.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class IacEmitContext:
    """Inputs handed to an IaC agent's emit() method."""

    infra_dir: Path
    title: str
    slug: str
    enable_observability: bool
    network_tier: str          # "public" | "vnet-integrated" | "private"
    language: str              # informational — agent may tune compute defaults


@dataclass
class IacEmitResult:
    """Bookkeeping returned to the runner after emit()."""

    files_written: list[str]
    deploy_bullets: list[str]


class IacAgent(Protocol):
    """Contract every IaC specialist must implement."""

    name: str                # e.g. "bicep", "terraform"
    display_name: str        # e.g. "Azure Bicep"
    file_extension: str      # e.g. ".bicep", ".tf"

    def emit(self, ctx: IacEmitContext) -> IacEmitResult:  # pragma: no cover
        ...
