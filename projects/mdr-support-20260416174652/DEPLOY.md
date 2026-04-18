# Deploy - MDR Arrangement Extraction Agent

## Prerequisites
- Azure subscription with quota for Azure OpenAI (e.g. gpt-5.2) and
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

## Bootstrap the hybrid AI Search index
The application now issues semantic + vector queries. After infrastructure
deployment, create the vector-capable index and seed it with the checked-in MDR sample corpus.

Recommended path:

```powershell
.\scripts\run_search_index.ps1 -ResourceGroupName rg-mdr-support-dev
```

What the wrapper does:
- Resolves `aiSearchEndpoint` and `openAiEndpoint` from the latest successful deployment in the resource group unless you pass them explicitly.
- Uses `sample-corpus/manifest.json` by default, so the workflow is demo-ready immediately.
- Calls `scripts/bootstrap_search_index.py`, which still remains the underlying implementation.

If you prefer to target a specific deployment record:

```powershell
.\scripts\run_search_index.ps1 `
  -ResourceGroupName rg-mdr-support-dev `
  -DeploymentName mdr-support-dev
```

If you want to run the Python script directly, the equivalent flow is:

```powershell
python .\scripts\bootstrap_search_index.py `
  --manifest .\sample-corpus\manifest.json `
  --search-endpoint "https://<search>.search.windows.net" `
  --openai-endpoint "https://<openai>.openai.azure.com/"
```

To create the index schema without seeding documents:

```powershell
.\scripts\run_search_index.ps1 -ResourceGroupName rg-mdr-support-dev -CreateOnly
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
