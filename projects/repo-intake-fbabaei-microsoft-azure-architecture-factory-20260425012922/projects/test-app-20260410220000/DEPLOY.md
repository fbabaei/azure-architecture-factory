# Deploy

## Prerequisites

- Python 3.11+
- Azure CLI logged in (`az login`)
- Optional: Docker Desktop if you want containerized local run
- Azure resources:
  - Resource Group
  - Azure App Service or Azure Container Apps
  - Azure Key Vault
  - Application Insights
  - your configured LLM provider

## Local Validation

1. From the project root, create and activate a virtual environment.
2. Install runtime dependencies.
3. Run tests to validate generated artifacts.

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest tests -q
```

## Required Environment Variables

- `APP_ENV=dev`
- `APPINSIGHTS_CONNECTION_STRING=<value>`
- `KEY_VAULT_URI=https://<vault-name>.vault.azure.net/`
- `COPILOT_MODEL_ENDPOINT=<endpoint>`
- `COPILOT_MODEL_DEPLOYMENT=<deployment-name>`

## Local Run

```bash
python -m uvicorn src.copilot_api.main:app --host 127.0.0.1 --port 8000 --reload
```

Health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

## Azure Deployment Outline

1. Create or reuse a resource group.
2. Provision hosting, identity, Key Vault access, and Application Insights.
3. Configure app settings from the environment variable list above.
4. Deploy source from this project path (test-app-20260410220000) as a Python web service.
5. Validate `/health` and `/api/copilot/ask` after deployment.

## Security Baseline

- Prefer managed identity over secrets where possible.
- Store only non-sensitive configuration in app settings.
- Keep all secrets in Key Vault and use least-privilege RBAC.
- Enable diagnostic logs and request tracing before go-live.
