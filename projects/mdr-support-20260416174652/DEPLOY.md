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

The Bicep template provisions an Azure Container Registry by default
(`provisionAcr=true`) and grants the workload's managed identity
`AcrPull` on it. You can run the deployment once before you have an
image — the Container App will start on a placeholder image, then pick
up your real image on the next `az containerapp update`.

### First deployment (provision the platform + ACR)

```powershell
az group create --name rg-mdr-support-dev --location eastus2
az deployment group create `
  --resource-group rg-mdr-support-dev `
  --template-file infra/main.bicep `
  --parameters environment=dev workloadName=mdr-support `
               enableObservability=true
```

Capture the ACR login server from the deployment outputs:

```powershell
$acr = az deployment group show -g rg-mdr-support-dev `
  -n main --query properties.outputs.containerRegistryLoginServer.value -o tsv
```

### Build and push the MDR agent image

```powershell
az acr login --name ($acr.Split('.')[0])
docker build -t "$acr/mdr-agent:1.0.0" .
docker push "$acr/mdr-agent:1.0.0"
```

### Redeploy with the real image

```powershell
az deployment group create `
  --resource-group rg-mdr-support-dev `
  --template-file infra/main.bicep `
  --parameters environment=dev workloadName=mdr-support `
               enableObservability=true `
               containerImage="$acr/mdr-agent:1.0.0"
```

Or update the Container App directly:

```powershell
az containerapp update `
  --resource-group rg-mdr-support-dev `
  --name mdr-support-dev-api `
  --image "$acr/mdr-agent:1.0.0"
```

### Using an existing registry

Set `provisionAcr=false` and pass your own `containerImage`. You are then
responsible for granting the managed identity `AcrPull` on the external
registry.

## Managed identity RBAC

RBAC is wired in Bicep — the following role assignments are created
automatically against the workload's user-assigned managed identity:

| Role | Scope | Resource type |
|------|-------|---------------|
| `Cognitive Services OpenAI User` | Azure OpenAI account | `Microsoft.Authorization/roleAssignments` |
| `Cognitive Services User` | Document Intelligence account | `Microsoft.Authorization/roleAssignments` |
| `Storage Blob Data Contributor` | Storage account | `Microsoft.Authorization/roleAssignments` |
| `Key Vault Secrets User` | Key Vault | `Microsoft.Authorization/roleAssignments` |
| `Search Index Data Reader` | Azure AI Search service | `Microsoft.Authorization/roleAssignments` |
| `AcrPull` | Container Registry (when `provisionAcr=true`) | `Microsoft.Authorization/roleAssignments` |
| `Cosmos DB Built-in Data Contributor` | Cosmos DB account (data plane) | `Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments` |

No manual `az role assignment create` calls are required.

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

## Optional: enable the Microsoft Agent Framework SDK runtime
The chat and extraction agents can be driven by the Microsoft Agent
Framework SDK (`agent-framework-core==1.0.0rc6`, backed by
`FoundryChatClient`). The preview stack has to be installed in two
phases because `azure-ai-agentserver-*` pins
`agent-framework-core<=rc3` and would otherwise win resolution. Use the
helper script to install them in the correct order:

```powershell
# Windows
.\scripts\install_agent_framework.ps1

# Linux / CI
./scripts/install_agent_framework.sh
```

The script runs the agentserver phase first, upgrades the
`agent-framework-*` packages to rc6, and verifies the import. On
success, set the following environment variables on the Container App:

| Variable | Value |
|----------|-------|
| `AGENT_FRAMEWORK_ENABLED` | `1` |
| `FOUNDRY_PROJECT_ENDPOINT` | `https://<project>.services.ai.azure.com/api/projects/<project>` |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME` | `gpt-5.2` (or your deployment name) |

> **Changing the chat model later:** run `./scripts/select_model.ps1`
> (local) or `./scripts/select_model.ps1 -Target azure -ContainerApp <app>
> -ResourceGroup <rg>` for a deployed app. It lists 5 models with
> price + trade-off info and updates `AZURE_OPENAI_DEPLOYMENT`
> accordingly. The same picker is available from the factory portal's
> **🤖 Select Model** button on each project card.

The user-assigned managed identity needs **Azure AI Developer** on the
Foundry project (for chat completion access) in addition to the existing
`Cognitive Services OpenAI User` role on the Azure OpenAI account. When
the SDK is not installed or the Foundry settings are missing, the
runtime transparently falls back to the deterministic local
implementation and logs a warning.

To create the index schema without seeding documents:

```powershell
.\scripts\run_search_index.ps1 -ResourceGroupName rg-mdr-support-dev -CreateOnly
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
