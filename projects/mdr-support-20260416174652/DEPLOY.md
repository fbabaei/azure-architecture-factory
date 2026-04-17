# Deploy - MDR Arrangement Extraction Agent

## Prerequisites
- Azure subscription with quota for Azure OpenAI (e.g. gpt-4o) and
  Document Intelligence in your target region.
- Azure AI Search capacity (Basic or Standard) for compliance knowledge
  retrieval.
- Azure CLI 2.60+ and Bicep CLI.
- Docker (for building the container image) and an Azure Container Registry
  or other OCI registry.

## Local dev (no Azure required)
```powershell
pip install -r requirements.txt
python -m uvicorn mdr_agent.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Hit http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs.

## Deploy infrastructure
```powershell
az group create --name rg-mdr-support-dev --location eastus2
az deployment group create `
  --resource-group rg-mdr-support-dev `
  --template-file infra/main.bicep `
  --parameters environment=dev workloadName=mdr-support `
               enableObservability=true `
               containerImage="<acr>.azurecr.io/mdr-agent:latest"
```

## Grant managed identity access
After the deployment, assign the following built-in roles to the
user-assigned managed identity (`<baseName>-mi`):

| Role | Scope |
|------|-------|
| `Cognitive Services OpenAI User` | Azure OpenAI account |
| `Cognitive Services User` | Document Intelligence account |
| `Storage Blob Data Contributor` | Storage account |
| `Cosmos DB Built-in Data Contributor` | Cosmos DB account |
| `Key Vault Secrets User` | Key Vault |
| `Search Index Data Reader` | Azure AI Search service |

```powershell
$mi = az identity show -g rg-mdr-support-dev -n mdr-support-dev-mi --query principalId -o tsv
# assign roles via az role assignment create ...
```

## Build & push the container
```powershell
docker build -t <acr>.azurecr.io/mdr-agent:latest .
az acr login --name <acr>
docker push <acr>.azurecr.io/mdr-agent:latest
```

Then re-run the deployment with the new image tag, or update the Container
App directly:
```powershell
az containerapp update `
  --resource-group rg-mdr-support-dev `
  --name mdr-support-dev-api `
  --image <acr>.azurecr.io/mdr-agent:latest
```

## Data topology
- Blob containers:
  - `mdr-documents` for uploaded source files.
  - `knowledge-base-source` for RAG source files.
- Cosmos containers:
  - `arrangements` for canonical draft state.
  - `sessions` for turn history.
  - `case-drafts` for editable case payload snapshots.
  - `audit-log` for immutable operational events.

## Validate
```powershell
$fqdn = az containerapp show -g rg-mdr-support-dev -n mdr-support-dev-api --query properties.configuration.ingress.fqdn -o tsv
curl "https://$fqdn/health"
```
