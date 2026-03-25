from __future__ import annotations

import os

from .config import Settings


class SecretResolver:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._secret_client = None

    def _get_secret_client(self):
        if self.settings.key_vault_url is None:
            return None
        if self._secret_client is not None:
            return self._secret_client

        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        self._secret_client = SecretClient(vault_url=self.settings.key_vault_url, credential=credential)
        return self._secret_client

    def resolve_direct_or_secret(self, direct_env_name: str, secret_name_env_name: str) -> str | None:
        direct_value = os.getenv(direct_env_name)
        if direct_value:
            return direct_value

        secret_name = os.getenv(secret_name_env_name)
        if not secret_name:
            return None

        secret_client = self._get_secret_client()
        if secret_client is None:
            return None

        return secret_client.get_secret(secret_name).value

    def require_direct_or_secret(self, direct_env_name: str, secret_name_env_name: str) -> str:
        value = self.resolve_direct_or_secret(direct_env_name, secret_name_env_name)
        if value is None:
            raise ValueError(
                f"Missing credential value. Set {direct_env_name} or {secret_name_env_name} (with Key Vault configured)."
            )
        return value
