from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_file: Path
    repository_backend: str
    storage_backend: str
    event_backend: str
    key_vault_url: str | None
    azure_cosmos_endpoint: str | None
    azure_cosmos_database: str
    azure_cosmos_container: str
    azure_storage_account_url: str | None
    azure_storage_connection_string: str | None
    azure_storage_container_prefix: str
    azure_event_grid_topic_endpoint: str | None
    allowed_data_classes: tuple[str, ...] = ("public", "internal", "confidential")

    @staticmethod
    def from_env(project_root: Path | None = None) -> "Settings":
        root = project_root or Path(__file__).resolve().parents[2]
        data_file = Path(os.getenv("REQUEST_DATA_FILE", root / "data" / "requests.json"))
        return Settings(
            project_root=root,
            data_file=data_file,
            repository_backend=os.getenv("REQUEST_REPOSITORY_BACKEND", "local").lower(),
            storage_backend=os.getenv("STORAGE_PROVISIONER_BACKEND", "local").lower(),
            event_backend=os.getenv("EVENT_PUBLISHER_BACKEND", "log").lower(),
            key_vault_url=os.getenv("AZURE_KEY_VAULT_URL"),
            azure_cosmos_endpoint=os.getenv("AZURE_COSMOS_ENDPOINT"),
            azure_cosmos_database=os.getenv("AZURE_COSMOS_DATABASE", "storage-self-service"),
            azure_cosmos_container=os.getenv("AZURE_COSMOS_CONTAINER", "requests"),
            azure_storage_account_url=os.getenv("AZURE_STORAGE_ACCOUNT_URL"),
            azure_storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            azure_storage_container_prefix=os.getenv("AZURE_STORAGE_CONTAINER_PREFIX", "sss"),
            azure_event_grid_topic_endpoint=os.getenv("AZURE_EVENT_GRID_TOPIC_ENDPOINT"),
        )
