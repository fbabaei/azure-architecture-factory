# Deploy

## Prerequisites

- Python 3.11+
- Azure CLI logged in (`az login`)
- Optional: Docker Desktop for containerized local validation
- Azure resources:
	- Resource Group
	- Azure App Service or Azure Container Apps
	- Azure Key Vault
	- Application Insights
	- Azure OpenAI or an approved enterprise LLM endpoint

## Local Validation

```bash
python -m venv .venv
.venv\\Scripts\\activate
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

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## Azure Deployment Outline

1. Create or select a target resource group.
2. Provision hosting, managed identity, Key Vault access, and Application Insights.
3. Set environment variables listed above in your target host.
4. Deploy this project as a Python web app.
5. Validate `/health` and `/api/copilot/ask` after deployment.

## Security Baseline

- Use managed identity where possible.
- Keep secrets in Key Vault.
- Apply least-privilege RBAC for app identity.
- Enable request and dependency tracing in Application Insights.
