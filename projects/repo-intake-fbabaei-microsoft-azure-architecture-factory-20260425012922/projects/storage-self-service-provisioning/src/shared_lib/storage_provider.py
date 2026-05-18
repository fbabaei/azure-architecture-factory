from __future__ import annotations

from .config import Settings
from .governance import build_adls_container_name, build_storage_name
from .models import ProvisioningRequest
from .secrets import SecretResolver


class LocalStorageProvisioner:
    def provision(self, request: ProvisioningRequest) -> dict[str, str]:
        storage_name = build_storage_name(request)
        container_name = build_adls_container_name(request)
        return {
            "storage_account": storage_name,
            "adls_container": container_name,
            "resource_group": f"rg-{request.project}-{request.environment}",
        }


class AzureBlobStorageProvisioner:
    def __init__(self, settings: Settings):
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        resolver = SecretResolver(settings)
        connection_string = resolver.resolve_direct_or_secret(
            "AZURE_STORAGE_CONNECTION_STRING",
            "AZURE_STORAGE_CONNECTION_STRING_SECRET_NAME",
        )

        if connection_string:
            self.client = BlobServiceClient.from_connection_string(connection_string)
        else:
            if settings.azure_storage_account_url is None:
                raise ValueError(
                    "AZURE_STORAGE_ACCOUNT_URL must be set when using azure storage provisioner backend"
                )
            self.client = BlobServiceClient(
                account_url=settings.azure_storage_account_url,
                credential=DefaultAzureCredential(),
            )
        self.container_prefix = settings.azure_storage_container_prefix

    def provision(self, request: ProvisioningRequest) -> dict[str, str]:
        from azure.core.exceptions import ResourceExistsError

        storage_name = build_storage_name(request)
        container_name = f"{self.container_prefix}-{build_adls_container_name(request)}"[:63]
        container_name = container_name.replace("_", "-")

        try:
            self.client.create_container(container_name)
        except ResourceExistsError:
            pass

        account_name = getattr(self.client, "account_name", "configured-account")
        return {
            "storage_account": account_name or storage_name,
            "adls_container": container_name,
            "resource_group": f"rg-{request.project}-{request.environment}",
        }


StorageProvisioner = LocalStorageProvisioner


def create_storage_provisioner(settings: Settings):
    if settings.storage_backend == "azure":
        return AzureBlobStorageProvisioner(settings)
    return LocalStorageProvisioner()
