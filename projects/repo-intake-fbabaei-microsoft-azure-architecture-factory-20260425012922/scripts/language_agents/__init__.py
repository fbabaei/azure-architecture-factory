"""Language specialist registry.

Adding a new language:
  1. Create `<lang>_agent.py` in this package exporting an `AGENT` instance.
  2. Add it to `_REGISTRY` below.
  3. Teach `resolve_from_brd` any alternate spellings you want to accept.

The runner calls `resolve_from_brd(markdown)` to pick an agent, then
`agent.emit(LanguageEmitContext(...))` to write the source code. Python is the
default when nothing matches — preserves pre-refactor behaviour.
"""
from __future__ import annotations

from .base import LanguageAgent, LanguageEmitContext, LanguageEmitResult
from .python_agent import AGENT as _PYTHON_AGENT
from .dotnet_agent import AGENT as _DOTNET_AGENT

__all__ = [
    "LanguageAgent",
    "LanguageEmitContext",
    "LanguageEmitResult",
    "resolve_from_brd",
    "get",
    "registered_names",
]

DEFAULT_NAME = "python"

_REGISTRY: dict[str, LanguageAgent] = {
    _PYTHON_AGENT.name: _PYTHON_AGENT,
    _DOTNET_AGENT.name: _DOTNET_AGENT,
}

# Alternate spellings that resolve to a canonical registry key.
_ALIASES: dict[str, str] = {
    "python": "python", "py": "python",
    "dotnet": "dotnet", "net": "dotnet", ".net": "dotnet",
    "csharp": "dotnet", "c#": "dotnet", "aspnet": "dotnet", "aspnetcore": "dotnet",
}


def get(name: str) -> LanguageAgent:
    """Return the agent for `name`, falling back to the default if unknown."""
    canonical = _ALIASES.get((name or "").strip().lower().lstrip("."), DEFAULT_NAME)
    return _REGISTRY.get(canonical, _REGISTRY[DEFAULT_NAME])


def registered_names() -> list[str]:
    return sorted(_REGISTRY.keys())


def resolve_from_brd(markdown: str) -> LanguageAgent:
    """Parse the BRD for `Implementation language: <lang>` (case-insensitive).

    Falls back to the default (Python) if the field is missing or unrecognised.
    """
    for line in markdown.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key_clean = key.strip().strip("*").strip().lower()
        if key_clean in {"implementation language", "language", "implementation.language"}:
            candidate = value.strip().strip("*").strip().strip("`").lower().lstrip(".")
            if candidate in _ALIASES:
                return _REGISTRY[_ALIASES[candidate]]
    return _REGISTRY[DEFAULT_NAME]
