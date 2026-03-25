# Storage Self-Service Provisioning Platform

This project defines a web-service-based platform for self-service storage provisioning on Azure, with strong access control, monitoring, and governance.

## Goals

- Allow authorized users to request storage resources through a web portal.
- Enforce access control via Microsoft Entra ID and role-based policies.
- Automate provisioning workflows with approval and auditability.
- Apply governance and data catalog controls with Microsoft Purview.
- Provide full observability through Azure Monitor.

## Core Platform Capabilities

- Self-service request intake (project, team, environment, data class).
- Policy-based provisioning for Storage Account and ADLS Gen2.
- Event-driven provisioning lifecycle and status updates.
- Secrets and configuration protection with Azure Key Vault.
- Centralized audit/state tracking for requests and operations.

## Architecture Artifact

- Diagram: `diagrams/azure-storage-self-service-architecture.drawio`
- Notes: `diagrams/azure-storage-self-service-architecture.md`

## Scope

This project contains architecture and design artifacts for implementation planning.

## Python Programs

- `src/provisioning_api/main.py`: FastAPI service for request intake and status retrieval.
- `src/workflow_worker/main.py`: worker that processes pending requests through validation, provisioning, and governance states.
- `src/shared_lib/*`: shared config, governance, models, repository, resilience, and monitoring helpers.
- `run_pipeline.py`: local sample runner that submits and processes one request.

## Run Locally

1. Install dependencies:
   - `pip install -r projects/storage-self-service-provisioning/requirements.txt`
2. Start the API:
   - `cd projects/storage-self-service-provisioning`
   - `set PYTHONPATH=src && uvicorn provisioning_api.main:app --reload`
3. In another terminal, process requests:
   - `cd projects/storage-self-service-provisioning`
   - `set PYTHONPATH=src && python src/workflow_worker/main.py`
4. Or run the sample end-to-end flow:
   - `python projects/storage-self-service-provisioning/run_pipeline.py`

## Tests

- `python -m unittest discover projects/storage-self-service-provisioning/tests`

## Azure SDK Integration Points

The implementation now supports pluggable backends behind provider/repository interfaces:

- Repository backend: `REQUEST_REPOSITORY_BACKEND=local|cosmos`
- Storage backend: `STORAGE_PROVISIONER_BACKEND=local|azure`
- Event backend: `EVENT_PUBLISHER_BACKEND=log|eventgrid`

### Cosmos DB

- `AZURE_COSMOS_ENDPOINT`
- `AZURE_COSMOS_DATABASE` (default: `storage-self-service`)
- `AZURE_COSMOS_CONTAINER` (default: `requests`)
- `AZURE_COSMOS_CONNECTION_STRING` or `AZURE_COSMOS_KEY`
- `AZURE_COSMOS_CONNECTION_STRING_SECRET_NAME` for Key Vault indirection
- `AZURE_COSMOS_KEY_SECRET_NAME` for Key Vault indirection

### Storage (Blob container provisioning)

- `AZURE_STORAGE_ACCOUNT_URL` or `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER_PREFIX` (default: `sss`)
- `AZURE_STORAGE_CONNECTION_STRING_SECRET_NAME` for Key Vault indirection

### Event Grid

- `AZURE_EVENT_GRID_TOPIC_ENDPOINT`
- `AZURE_EVENT_GRID_TOPIC_KEY` or `AZURE_EVENT_GRID_TOPIC_KEY_SECRET_NAME`

### Key Vault

- `AZURE_KEY_VAULT_URL`

When `AZURE_KEY_VAULT_URL` is provided, secret-name environment variables are resolved via Key Vault using managed identity (`DefaultAzureCredential`).
