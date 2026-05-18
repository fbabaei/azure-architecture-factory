from __future__ import annotations

import json
import importlib
import os
import sys
from pathlib import Path


def _setup_imports() -> Path:
    project_root = Path(__file__).resolve().parent
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    return project_root


def run_sample() -> None:
    project_root = _setup_imports()
    os.environ.setdefault("REQUEST_DATA_FILE", str(project_root / "data" / "requests.json"))

    models_module = importlib.import_module("shared_lib.models")
    api_module = importlib.import_module("provisioning_api.main")
    worker_module = importlib.import_module("workflow_worker.main")
    config_module = importlib.import_module("shared_lib.config")
    repository_module = importlib.import_module("shared_lib.repository")

    ProvisioningRequestCreate = models_module.ProvisioningRequestCreate
    create_request = api_module.create_request
    process_pending_requests = worker_module.process_pending_requests
    Settings = config_module.Settings
    RequestRepository = repository_module.RequestRepository

    payload = ProvisioningRequestCreate(
        project="datalab",
        team="platform",
        environment="dev",
        data_class="internal",
    )

    request = create_request(payload)
    print(f"Created request: {request.request_id}")

    processed = process_pending_requests()
    print(f"Processed requests: {processed}")

    repository = RequestRepository(Settings.from_env(project_root).data_file)
    final_state = repository.get(request.request_id)
    if final_state is None:
        raise RuntimeError("Request not found after processing")

    print(json.dumps(final_state.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    run_sample()
