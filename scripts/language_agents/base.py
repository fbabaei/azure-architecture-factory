"""Shared contract for language specialist agents.

A language agent owns the emission of application source code, tests, build
tooling (requirements.txt / .csproj / etc.), README, and DEPLOY docs for a
single implementation language.

Adding a new language means:
  1. Create `scripts/language_agents/<lang>_agent.py` exporting a LanguageAgent
     instance named `AGENT`.
  2. Register it in `scripts/language_agents/__init__.py`.
No other runner changes required.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class LanguageEmitContext:
    """Inputs handed to a language agent's emit() method."""

    project_root: Path
    tests_dir: Path
    title: str
    slug: str
    source_brd: str
    requirements: list[str]
    enable_observability: bool


@dataclass
class LanguageEmitResult:
    """Bookkeeping returned to the runner after emit()."""

    files_written: list[str]
    readme_bullets: list[str]
    # Main application entrypoint (repo-relative, forward slashes).
    # Used by the runner when building the traceability matrix so
    # the "Starter API" row points at the actual emitted file
    # (e.g. src/mdr_support/main.py, src/Program.cs).
    primary_source_path: str = "src/copilot_api/main.py"


class LanguageAgent(Protocol):
    """Contract every language specialist must implement."""

    name: str                # e.g. "python", "dotnet"
    display_name: str        # e.g. "Python (FastAPI)"

    def emit(self, ctx: LanguageEmitContext) -> LanguageEmitResult:  # pragma: no cover
        ...
