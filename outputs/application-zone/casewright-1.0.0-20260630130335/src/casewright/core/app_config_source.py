"""Azure App Configuration custom pydantic-settings v2 source.

Keep ``.env`` (or Azure App Service application settings) minimal — just the
bootstrap variables needed to locate the store::

    APP_CONFIG_ENDPOINT=https://<store>.azconfig.io   # managed identity auth
    APP_CONFIG_KEY_FILTER=casewright:*                 # key prefix in the store
    APP_CONFIG_LABEL_FILTER=production                 # environment label

All other settings are stored in Azure App Configuration under keys that match
the environment-variable names (field aliases) used by :class:`Settings`, e.g.::

    casewright:SEARCHSERVICE_ENDPOINT → Settings.search_endpoint
    casewright:COSMOS_ENDPOINT        → Settings.cosmos_endpoint

Key Vault references stored in App Configuration are automatically resolved
using the same ``DefaultAzureCredential`` (managed identity) — consistent with
Casewright's no-secrets, managed-identity-only posture.

Source priority (highest → lowest):

1. init kwargs (explicit overrides in tests / code)
2. Environment variables  (still allow env-var overrides in CI/CD)
3. Azure App Configuration  ← this source
4. .env file  (local development defaults)
5. File secrets directory

When ``APP_CONFIG_ENDPOINT`` is unset the source returns an empty dict and adds
zero overhead beyond a single ``os.getenv`` call.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

logger = logging.getLogger(__name__)

# Sentinel so we can distinguish "not yet loaded" from "loaded but empty".
_UNSET: object = object()
_loaded_config: Any = _UNSET  # dict[str, Any] after first load


def _load_app_config() -> dict[str, Any]:
    """Load every key-value pair from Azure App Configuration.

    The result is cached at module level so the network round-trip happens at
    most once per process. Returns an empty dict when ``APP_CONFIG_ENDPOINT``
    is not set.
    """
    global _loaded_config
    if _loaded_config is not _UNSET:
        return _loaded_config  # type: ignore[return-value]

    endpoint: str | None = os.getenv("APP_CONFIG_ENDPOINT")

    if not endpoint:
        logger.debug(
            "APP_CONFIG_ENDPOINT not set — Azure App Configuration disabled; "
            "falling back to environment variables and .env file."
        )
        _loaded_config = {}
        return _loaded_config

    try:
        from azure.appconfiguration.provider import (  # type: ignore[import]
            AzureAppConfigurationKeyVaultOptions,
            SettingSelector,
            load,
        )
        from azure.identity import DefaultAzureCredential

        key_filter: str = os.getenv("APP_CONFIG_KEY_FILTER", "*")
        # Explicit label wins; fall back to the general ENVIRONMENT variable so
        # that setting ENVIRONMENT=production is enough.
        label_filter: str | None = (
            os.getenv("APP_CONFIG_LABEL_FILTER") or os.getenv("ENVIRONMENT") or None
        )

        if label_filter:
            selects = [
                SettingSelector(key_filter=key_filter),  # shared / no-label defaults
                SettingSelector(key_filter=key_filter, label_filter=label_filter),  # env overlay
            ]
        else:
            selects = [SettingSelector(key_filter=key_filter)]

        # Derive the trim prefix from the key filter so trimmed keys match the
        # env-var aliases: "casewright:*" → trim "casewright:".
        prefix_to_trim = key_filter.rstrip("*") if key_filter != "*" else None
        trim_prefixes = [prefix_to_trim] if prefix_to_trim else []

        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)

        cfg = load(
            endpoint=endpoint,
            credential=credential,
            selects=selects,
            trim_prefixes=trim_prefixes,
            key_vault_options=AzureAppConfigurationKeyVaultOptions(credential=credential),
        )
        _loaded_config = dict(cfg)
        logger.info(
            "Loaded %d key(s) from Azure App Configuration (endpoint=%s, label=%s).",
            len(_loaded_config),
            endpoint,
            label_filter or "(no label)",
        )

    except ImportError:
        logger.warning(
            "azure-appconfiguration-provider is not installed; skipping Azure App "
            "Configuration. Install it with: pip install 'azure-appconfiguration-provider>=2.1.0'"
        )
        _loaded_config = {}
    except Exception:
        logger.exception(
            "Failed to load Azure App Configuration; continuing with environment "
            "variables / .env."
        )
        _loaded_config = {}

    return _loaded_config  # type: ignore[return-value]


def reset_app_config_cache() -> None:
    """Clear the module-level cache, forcing a fresh load on the next call.

    Intended for tests that inject different App Configuration values between
    cases.
    """
    global _loaded_config
    _loaded_config = _UNSET


def _expected_key(field_name: str, field_info: FieldInfo, env_prefix: str) -> str:
    """Compute the App Configuration key for a settings field.

    Casewright's fields declare an explicit ``alias`` (the env-var name), so the
    alias takes precedence. Falls back to ``env_prefix`` + field name to remain
    compatible with prefix-style settings classes.
    """
    alias = field_info.alias or field_info.validation_alias
    if isinstance(alias, str) and alias:
        return alias.upper()
    return (env_prefix + field_name).upper()


class AzureAppConfigSource(PydanticBaseSettingsSource):
    """pydantic-settings v2 source backed by Azure App Configuration.

    For each field the source computes the expected key (field alias, or
    ``env_prefix`` + field name) and performs a case-insensitive lookup in the
    loaded App Configuration mapping. Found values are type-coerced through the
    same path used by the built-in ``EnvSettingsSource``.
    """

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        """Required by the base class; individual lookups are done in ``__call__``."""
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        config = _load_app_config()
        if not config:
            return {}

        env_prefix: str = self.settings_cls.model_config.get("env_prefix", "") or ""
        # Case-insensitive view of the store.
        upper_config = {k.upper(): v for k, v in config.items()}
        result: dict[str, Any] = {}

        for field_name, field_info in self.settings_cls.model_fields.items():
            key = _expected_key(field_name, field_info, env_prefix)
            if key in upper_config and upper_config[key] is not None:
                # Store under the field's alias when present so pydantic maps it
                # back to the correct field; otherwise use the field name.
                alias = field_info.alias if isinstance(field_info.alias, str) else None
                result[alias or field_name] = upper_config[key]

        return result


class AppConfigAwareSettings(BaseSettings):
    """``BaseSettings`` subclass that injects Azure App Configuration as a source.

    Inherit from this class instead of ``BaseSettings`` for any settings class
    that should load values from Azure App Configuration when
    ``APP_CONFIG_ENDPOINT`` is set.

    Source priority (highest → lowest):

    1. ``init_settings``    — explicit constructor kwargs (useful in tests)
    2. ``env_settings``     — process environment variables
    3. ``AzureAppConfigSource`` ← **this class injects it here**
    4. ``dotenv_settings``  — ``.env`` file (local dev defaults)
    5. ``file_secret_settings`` — secrets directory
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            AzureAppConfigSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
