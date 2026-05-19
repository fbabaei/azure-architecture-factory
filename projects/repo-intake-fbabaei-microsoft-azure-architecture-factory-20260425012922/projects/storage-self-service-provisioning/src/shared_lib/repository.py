from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .config import Settings
from .models import ProvisioningRequest, RequestStatus
from .secrets import SecretResolver


class RequestRepositoryInterface(Protocol):
    def create(self, request: ProvisioningRequest) -> ProvisioningRequest: ...
    def list_all(self) -> list[ProvisioningRequest]: ...
    def get(self, request_id: str) -> ProvisioningRequest | None: ...
    def list_by_status(self, status: RequestStatus) -> list[ProvisioningRequest]: ...
    def update_status(self, request_id: str, status: RequestStatus, message: str) -> ProvisioningRequest: ...
    def attach_resources(self, request_id: str, resources: dict[str, str]) -> ProvisioningRequest: ...


class LocalFileRequestRepository:
    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.data_file.write_text("[]", encoding="utf-8")

    def _read_all(self) -> list[dict]:
        return json.loads(self.data_file.read_text(encoding="utf-8"))

    def _write_all(self, rows: list[dict]) -> None:
        self.data_file.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

    def create(self, request: ProvisioningRequest) -> ProvisioningRequest:
        rows = self._read_all()
        rows.append(request.model_dump(mode="json"))
        self._write_all(rows)
        return request

    def list_all(self) -> list[ProvisioningRequest]:
        return [ProvisioningRequest.model_validate(row) for row in self._read_all()]

    def get(self, request_id: str) -> ProvisioningRequest | None:
        for row in self._read_all():
            if row["request_id"] == request_id:
                return ProvisioningRequest.model_validate(row)
        return None

    def list_by_status(self, status: RequestStatus) -> list[ProvisioningRequest]:
        return [request for request in self.list_all() if request.status == status]

    def update_status(self, request_id: str, status: RequestStatus, message: str) -> ProvisioningRequest:
        rows = self._read_all()
        now = datetime.now(timezone.utc).isoformat()
        updated_row = None
        for row in rows:
            if row["request_id"] == request_id:
                row["status"] = status.value
                row["updated_at"] = now
                row.setdefault("status_history", []).append(
                    {"status": status.value, "at": now, "message": message}
                )
                updated_row = row
                break
        if updated_row is None:
            raise KeyError(f"Request not found: {request_id}")
        self._write_all(rows)
        return ProvisioningRequest.model_validate(updated_row)

    def attach_resources(self, request_id: str, resources: dict[str, str]) -> ProvisioningRequest:
        rows = self._read_all()
        now = datetime.now(timezone.utc).isoformat()
        updated_row = None
        for row in rows:
            if row["request_id"] == request_id:
                row["resources"] = resources
                row["updated_at"] = now
                updated_row = row
                break
        if updated_row is None:
            raise KeyError(f"Request not found: {request_id}")
        self._write_all(rows)
        return ProvisioningRequest.model_validate(updated_row)


class CosmosRequestRepository:
    def __init__(self, settings: Settings):
        from azure.cosmos import CosmosClient, PartitionKey
        from azure.identity import DefaultAzureCredential

        resolver = SecretResolver(settings)
        connection_string = resolver.resolve_direct_or_secret(
            "AZURE_COSMOS_CONNECTION_STRING",
            "AZURE_COSMOS_CONNECTION_STRING_SECRET_NAME",
        )

        if connection_string:
            client = CosmosClient.from_connection_string(connection_string)
        else:
            if settings.azure_cosmos_endpoint is None:
                raise ValueError("AZURE_COSMOS_ENDPOINT must be set for cosmos repository backend")
            cosmos_key = resolver.resolve_direct_or_secret("AZURE_COSMOS_KEY", "AZURE_COSMOS_KEY_SECRET_NAME")
            credential = cosmos_key if cosmos_key else DefaultAzureCredential()
            client = CosmosClient(url=settings.azure_cosmos_endpoint, credential=credential)

        database = client.create_database_if_not_exists(id=settings.azure_cosmos_database)
        self.container = database.create_container_if_not_exists(
            id=settings.azure_cosmos_container,
            partition_key=PartitionKey(path="/partitionKey"),
        )

    def _to_item(self, request: ProvisioningRequest) -> dict:
        payload = request.model_dump(mode="json")
        return {
            "id": request.request_id,
            "partitionKey": request.request_id,
            "payload": payload,
        }

    def create(self, request: ProvisioningRequest) -> ProvisioningRequest:
        self.container.upsert_item(self._to_item(request))
        return request

    def list_all(self) -> list[ProvisioningRequest]:
        rows = self.container.query_items(
            query="SELECT c.payload FROM c",
            enable_cross_partition_query=True,
        )
        return [ProvisioningRequest.model_validate(row["payload"]) for row in rows]

    def get(self, request_id: str) -> ProvisioningRequest | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError

        try:
            item = self.container.read_item(item=request_id, partition_key=request_id)
        except CosmosResourceNotFoundError:
            return None
        return ProvisioningRequest.model_validate(item["payload"])

    def list_by_status(self, status: RequestStatus) -> list[ProvisioningRequest]:
        rows = self.container.query_items(
            query="SELECT c.payload FROM c WHERE c.payload.status = @status",
            parameters=[{"name": "@status", "value": status.value}],
            enable_cross_partition_query=True,
        )
        return [ProvisioningRequest.model_validate(row["payload"]) for row in rows]

    def _replace_payload(self, request_id: str, transform):
        found = self.container.read_item(item=request_id, partition_key=request_id)
        payload = found["payload"]
        updated_payload = transform(payload)
        found["payload"] = updated_payload
        self.container.replace_item(item=request_id, body=found)
        return ProvisioningRequest.model_validate(updated_payload)

    def update_status(self, request_id: str, status: RequestStatus, message: str) -> ProvisioningRequest:
        now = datetime.now(timezone.utc).isoformat()

        def transform(payload: dict) -> dict:
            payload["status"] = status.value
            payload["updated_at"] = now
            payload.setdefault("status_history", []).append(
                {"status": status.value, "at": now, "message": message}
            )
            return payload

        return self._replace_payload(request_id, transform)

    def attach_resources(self, request_id: str, resources: dict[str, str]) -> ProvisioningRequest:
        now = datetime.now(timezone.utc).isoformat()

        def transform(payload: dict) -> dict:
            payload["resources"] = resources
            payload["updated_at"] = now
            return payload

        return self._replace_payload(request_id, transform)


RequestRepository = LocalFileRequestRepository


def create_request_repository(settings: Settings) -> RequestRepositoryInterface:
    if settings.repository_backend == "cosmos":
        return CosmosRequestRepository(settings)
    return LocalFileRequestRepository(settings.data_file)
