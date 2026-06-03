"""Shared pytest fixtures for the Casewright test suite."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Ensure each test sees a fresh Settings instance."""
    from casewright.core.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
