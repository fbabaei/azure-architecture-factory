from __future__ import annotations

from shared_lib.config import Settings
from shared_lib.governance import validate_request_policy
from shared_lib.models import RequestStatus
from shared_lib.monitoring import create_event_publisher
from shared_lib.repository import create_request_repository
from shared_lib.resilience import with_retry
from shared_lib.storage_provider import create_storage_provisioner


def process_pending_requests() -> int:
    settings = Settings.from_env()
    repository = create_request_repository(settings)
    provisioner = create_storage_provisioner(settings)
    event_publisher = create_event_publisher(settings)

    pending = repository.list_by_status(RequestStatus.pending)
    processed_count = 0

    for request in pending:
        request_id = request.request_id
        try:
            repository.update_status(request_id, RequestStatus.validating, "Governance validation started")
            validate_request_policy(request, settings)

            repository.update_status(request_id, RequestStatus.provisioning, "Provisioning started")
            resources = with_retry(lambda: provisioner.provision(request), retries=3, delay_seconds=0.1)
            repository.attach_resources(request_id, resources)

            repository.update_status(request_id, RequestStatus.governed, "Governance registration complete")
            repository.update_status(request_id, RequestStatus.completed, "Provisioning completed")
            event_publisher.publish(request_id, "RequestCompleted", "Storage resources provisioned")
        except Exception as exc:  # noqa: BLE001
            repository.update_status(request_id, RequestStatus.failed, f"Provisioning failed: {exc}")
            event_publisher.publish(request_id, "RequestFailed", str(exc))
        processed_count += 1

    return processed_count


if __name__ == "__main__":
    count = process_pending_requests()
    print(f"Processed {count} pending requests")
