"""Factory runtime: an in-repo consumer of the Agent Framework pattern.

This package is the factory's own adoption of
``docs/AGENT_FRAMEWORK_RUNTIME_PATTERN.md``. It classifies BRDs to
recommend which runtime a generated project should ship
(``local`` vs ``agent-framework``) and is the authoritative resolver for
the orchestrator's ``runtime: auto`` argument.

It ships with two interchangeable runtimes behind one API:

- :class:`LocalProjectClassifier` - deterministic keyword-based
  classifier. Always available. Default.
- :class:`FoundryProjectClassifier` - Agent Framework SDK-backed
  classifier. Opt-in via ``FACTORY_AGENT_FRAMEWORK_ENABLED=1`` plus the
  standard Foundry env flags. Falls back to the local classifier if
  the SDK is not installed.

Use :func:`build_classifier` to pick the right runtime. See
``tests/test_project_classifier.py`` for the mandatory test shapes.
"""
from .project_classifier import (
    ClassificationResult,
    FoundryProjectClassifier,
    LocalProjectClassifier,
    ProjectClassifier,
    build_classifier,
    classify_brd,
)
from .brd_readiness import BRDReadinessResult, ReadinessCheckResult, assess_brd_readiness
from .settings import FactorySettings

__all__ = [
    "ClassificationResult",
    "BRDReadinessResult",
    "FactorySettings",
    "FoundryProjectClassifier",
    "LocalProjectClassifier",
    "ProjectClassifier",
    "ReadinessCheckResult",
    "assess_brd_readiness",
    "build_classifier",
    "classify_brd",
]
