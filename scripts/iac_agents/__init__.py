"""IaC specialist registry.

Adding a new IaC tool:
  1. Create `<tool>_agent.py` in this package exporting an `AGENT` instance.
  2. Add it to `_REGISTRY` below.
  3. Teach `resolve_from_brd` any alternate spellings you want to accept.

Bicep is the default when nothing matches — preserves pre-refactor behaviour.
"""
from __future__ import annotations

from .base import IacAgent, IacEmitContext, IacEmitResult
from .bicep_agent import AGENT as _BICEP_AGENT
from .terraform_agent import AGENT as _TERRAFORM_AGENT

__all__ = [
    "IacAgent",
    "IacEmitContext",
    "IacEmitResult",
    "resolve_from_brd",
    "get",
    "registered_names",
]

DEFAULT_NAME = "bicep"

_REGISTRY: dict[str, IacAgent] = {
    _BICEP_AGENT.name: _BICEP_AGENT,
    _TERRAFORM_AGENT.name: _TERRAFORM_AGENT,
}

_ALIASES: dict[str, str] = {
    "bicep": "bicep", "azure bicep": "bicep",
    "terraform": "terraform", "tf": "terraform", "hcl": "terraform", "azurerm": "terraform",
}


def get(name: str) -> IacAgent:
    canonical = _ALIASES.get((name or "").strip().lower(), DEFAULT_NAME)
    return _REGISTRY.get(canonical, _REGISTRY[DEFAULT_NAME])


def registered_names() -> list[str]:
    return sorted(_REGISTRY.keys())


def resolve_from_brd(markdown: str) -> IacAgent:
    """Parse the BRD for `Infrastructure as code: <tool>` / `IaC: <tool>`.

    Falls back to the default (Bicep) if the field is missing or unrecognised.
    """
    keys = {
        "infrastructure as code",
        "infrastructure-as-code",
        "iac",
        "iac tool",
        "infrastructure tool",
        "infrastructure",
    }
    for line in markdown.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key_clean = key.strip().strip("*").strip().lower()
        if key_clean in keys:
            candidate = value.strip().strip("*").strip().strip("`").lower()
            if candidate in _ALIASES:
                return _REGISTRY[_ALIASES[candidate]]
    return _REGISTRY[DEFAULT_NAME]
