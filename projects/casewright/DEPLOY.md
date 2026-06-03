# Deploying Casewright

This guide deploys the full Casewright stack to Azure using the Bicep templates in `infra/`.

## Prerequisites

- Azure CLI 2.60+ with the Bicep CLI (`az bicep version`)
- An Azure subscription and permission to create resource groups and assign roles
  (Owner or User Access Administrator on the target resource group, since the deployment
  creates role assignments)
- Docker (to build and push the API and worker container images)
- A Microsoft Entra app registration for SharePoint/Graph access (tenant + client id)

## Option A: Azure Developer CLI (`azd up`)

The repository includes an [azure.yaml](azure.yaml) service map that lets the Azure Developer
CLI build the container images and deploy all three services (`casewright-api`,
`casewright-worker`, `casewright-scheduler`) against the Bicep infrastructure in one step:

```pwsh
azd auth login
azd up
```

`azd` provisions the infrastructure, builds and pushes the images to the provisioned
registry, and deploys each service to its target host. Use the manual Bicep flow below
(Option B) when you need finer control over image build/push or per-environment parameters.

## Option B: Manual Bicep deployment

### 1. Select a subscription

```pwsh
az login
az account set --subscription "<subscription-id>"
```

### 2. Create the resource group

```pwsh
az group create -n rg-casewright-dev -l eastus2
```

### 3. Build and push container images

The API and worker share one image (`src/Dockerfile`); the worker overrides the start
command. Build, then push to the Azure Container Registry created by the deployment, or to an
existing registry referenced in the parameter file.

```pwsh
# Initial bootstrap: deploy infra once with the placeholder images, then push real images
# to the provisioned registry and redeploy with the real image references.

cd src
docker build -t casewright-api:latest -f Dockerfile .
```

After the registry exists (see step 4), tag and push:

```pwsh
$acr = az deployment group show -g rg-casewright-dev -n main `
  --query properties.outputs.registryLoginServer.value -o tsv

az acr login -n ($acr.Split('.')[0])
docker tag casewright-api:latest "$acr/casewright-api:latest"
docker tag casewright-api:latest "$acr/casewright-worker:latest"
docker push "$acr/casewright-api:latest"
docker push "$acr/casewright-worker:latest"
```

### 4. Deploy infrastructure

Edit `infra/params/dev.bicepparam` and set:

- `apiImage` / `workerImage` — the pushed image references (or leave the placeholder for the
  first bootstrap pass)
- `graphTenantId`, `graphClientId` — your Entra app registration values
- `syncDefaultTenantId` — the default tenant id used for scheduled syncs

```pwsh
az deployment group create `
  -g rg-casewright-dev `
  -f infra/main.bicep `
  -p infra/params/dev.bicepparam
```

Validate before deploying:

```pwsh
az deployment group what-if `
  -g rg-casewright-dev `
  -f infra/main.bicep `
  -p infra/params/dev.bicepparam
```

### 5. Redeploy with real images

After pushing the real images (step 3), update `apiImage` / `workerImage` in the parameter
file and re-run the `az deployment group create` command from step 4. Role assignments and
all other resources are idempotent.

### 6. Configure the agent and pipeline

Once the API is running, configure the Foundry agent endpoint/id via the deployment outputs
or app settings, then initialize the ingestion pipeline:

```pwsh
$api = az deployment group show -g rg-casewright-dev -n main `
  --query properties.outputs.apiFqdn.value -o tsv

# Create / update the data source, index, skillsets, and indexers
curl -X POST "https://$api/api/pipeline/setup-pipeline"

# Trigger an initial SharePoint sync
curl -X POST "https://$api/api/sharepoint/sites/sync"
```

### 7. Provision the Foundry IQ knowledge base + hosted agent

Query-time retrieval runs through a **Foundry IQ knowledge base** (`casewright-kb`) over the
`casewright-index`, invoked by a hosted `case-knowledge-agent` via an MCP RemoteTool
connection (see ADR-10). Provisioning is one-shot and is done after the index exists (step 6)
and the Foundry project endpoint is known.

Set the required environment variables (or `.env`), then run the deploy script:

```pwsh
$env:SEARCHSERVICE_ENDPOINT   = "https://<search>.search.windows.net"
$env:FOUNDRY_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:AZURE_OPENAI_ENDPOINT    = "https://<aoai>.openai.azure.com"
# Project resource id is auto-derived from the endpoint + the two below, or set it explicitly:
$env:AZURE_SUBSCRIPTION_ID    = "<sub-id>"
$env:AZURE_RESOURCE_GROUP     = "rg-casewright-dev"

python scripts/deploy_agent.py deploy
```

This (1) creates/updates the knowledge source + knowledge base on the search service,
(2) creates/updates the `casewright-kb-mcp` RemoteTool project connection, and (3) creates the
hosted agent and prints its id. Set `FOUNDRY_AGENT_ID` (and `FOUNDRY_PROJECT_ENDPOINT`) on the
API + worker container apps to that id to route runtime traffic through Foundry; otherwise the
service falls back to the in-process hybrid query. Tunables live under `SEARCH_KB_*` and
`FOUNDRY_KB_CONNECTION_NAME` (see `.env.example`).

Useful flags: `--knowledge-base-only` (provision the KB without the agent),
`--skip-knowledge-base` (only wire the connection + agent), and
`delete --agent-id <id> [--delete-knowledge-base]` to tear down.

> The caller needs **Search Service Contributor** on the search service to provision the KB,
> and the search service's identity needs **Cognitive Services OpenAI User** on the Azure
> OpenAI resource so the KB can call the embedding/answer model.

## Environments

| Environment | Parameter file |
| --- | --- |
| Dev | `infra/params/dev.bicepparam` |
| Test | `infra/params/test.bicepparam` |
| Prod | `infra/params/prod.bicepparam` |

Use the matching parameter file and a per-environment resource group
(`rg-casewright-test`, `rg-casewright-prod`).

## Deployment outputs

| Output | Description |
| --- | --- |
| `apiFqdn` | Public FQDN of the API container app |
| `registryLoginServer` | Container registry login server |
| `searchEndpoint` | Azure AI Search endpoint |
| `openAiEndpoint` | Azure OpenAI endpoint |
| `cosmosEndpoint` | Cosmos DB endpoint |

## Observability

The deployment wires `APPLICATIONINSIGHTS_CONNECTION_STRING` into the API and worker. When
that value is present, the app emits OpenTelemetry traces and custom metrics
(`casewright.sync.runs`, `casewright.sync.net_changes`, `casewright.indexer.runs`,
`casewright.messages.deadlettered`) to Application Insights. Instrumentation is fully opt-in:
if the connection string or the `azure-monitor-opentelemetry` package is absent, telemetry is
a no-op and the app runs unchanged.
| `serviceBusFqdn` | Service Bus namespace FQDN |
| `storageBlobEndpoint` | Storage blob endpoint |
| `keyVaultUri` | Key Vault URI |
| `functionAppName` | Scheduler Function App name |
| `apiIdentityClientId` / `workerIdentityClientId` / `schedulerIdentityClientId` | User-assigned identity client ids |
