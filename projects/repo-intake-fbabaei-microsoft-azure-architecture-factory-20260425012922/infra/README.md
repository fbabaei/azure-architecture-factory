# Bicep Infrastructure as Code

This folder contains production-ready Bicep templates for deploying the Azure AI Foundry Agentic Application to Azure.

## Architecture

The deployment is organized as a modular Bicep infrastructure covering the complete Azure AI Foundry architecture:

```
Compute Layer              AI & Data Layer                Security & Monitoring
├── Container Apps Env     ├── Azure AI Foundry         ├── Key Vault
├── Container App (Agent)  ├── AI Search                ├── Managed Identity
                           ├── Blob Storage             ├── App Insights
                           └── Cosmos DB                └── Log Analytics
```

## Folder Structure

```
infra/
├── main.bicep                          # Main orchestrator (entry point)
├── modules/
│   ├── compute/
│   │   └── containerappenv.bicep       # Container Apps environment & app
│   ├── ai/
│   │   └── search.bicep                # Azure AI Search
│   ├── data/
│   │   ├── storage.bicep               # Blob Storage
│   │   └── cosmosdb.bicep              # Cosmos DB (conversations, state)
│   ├── security/
│   │   ├── managed-identity.bicep      # User-assigned identity
│   │   └── keyvault.bicep              # Key Vault (secrets, API keys)
│   └── monitoring/
│       ├── log-analytics.bicep         # Log Analytics Workspace
│       └── appinsights.bicep           # Application Insights
└── params/
    ├── dev.bicepparam                  # Parameters for development
    ├── test.bicepparam                 # Parameters for testing
    └── prod.bicepparam                 # Parameters for production
```

## Module Design

Each module is independently deployable and returns outputs needed by other modules.

### Modules by Tier

#### Compute (`modules/compute/`)
- **containerappenv.bicep**
  - Creates Container Apps environment with Log Analytics integration
  - Deploys Container App with managed identity
  - Configures auto-scaling (CPU/memory-based)
  - Sets environment variables for app configuration
  - Outputs: Container App FQDN, Container App ID

#### AI & Data (`modules/ai/`, `modules/data/`)
- **search.bicep**
  - Deploys Azure AI Search service
  - Creates RBAC role assignment for managed identity
  - Supports multiple SKUs (basic, standard) by environment
  - Outputs: Search endpoint, service ID

- **storage.bicep**
  - Deploys Blob Storage with Hot tier
  - Creates default `documents` container
  - Assigns Storage Blob Data Contributor RBAC role
  - Outputs: Primary blob endpoint, storage account name

- **cosmosdb.bicep**
  - Deploys Cosmos DB SQL API account
  - Creates `agent-db` database
  - Creates two collections: `conversations` (TTL: 30 days) and `state`
  - Configures partitioning and indexing
  - Assigns Cosmos DB Built-in Data Contributor RBAC role
  - Outputs: Account endpoint, database name

#### Security (`modules/security/`)
- **managed-identity.bicep**
  - Creates user-assigned managed identity
  - No RBAC assignments (delegated to main.bicep for clarity)
  - Outputs: Identity ID, principal ID, client ID

- **keyvault.bicep**
  - Deploys Key Vault with Standard SKU
  - Configures access policies for managed identity
  - Enables deployment and template access
  - Outputs: Vault URI, Key Vault ID

#### Monitoring (`modules/monitoring/`)
- **log-analytics.bicep**
  - Creates Log Analytics Workspace
  - 30-day retention by default
  - Outputs: Workspace ID, customer ID

- **appinsights.bicep**
  - Creates Application Insights linked to Log Analytics
  - Instrumentation key and connection string for agent
  - Outputs: Instrumentation key, connection string

## Deployment

### Prerequisites

1. **Azure CLI**: Install the latest version
2. **Bicep CLI**: Latest version (included with Azure CLI 2.53.0+)
3. **Azure Subscription**: Valid subscription with appropriate permissions

### Steps

#### 1. Prepare Parameters

Edit the parameter file for your environment:

```bash
# For development
code infra/params/dev.bicepparam

# For production
code infra/params/prod.bicepparam
```

Update:
- `location`: Azure region (eastus, westus, etc.)
- `containerImageUri`: Container registry image URI (for test/prod)
- `projectName`: Customize the resource naming prefix
- `containerPort`: Application port (default: 8000)

#### 2. Create Resource Group

```bash
# For development
az group create \
  --name ai-agent-dev-rg \
  --location eastus

# For production
az group create \
  --name ai-agent-prod-rg \
  --location eastus
```

#### 3. Validate Deployment

```bash
# For development
az deployment group validate \
  --name ai-agent-dev-deployment \
  --resource-group ai-agent-dev-rg \
  --template-file infra/main.bicep \
  --parameters infra/params/dev.bicepparam

# For production
az deployment group validate \
  --name ai-agent-prod-deployment \
  --resource-group ai-agent-prod-rg \
  --template-file infra/main.bicep \
  --parameters infra/params/prod.bicepparam
```

#### 4. Deploy Infrastructure

```bash
# For development (watch progress)
az deployment group create \
  --name ai-agent-dev-deployment \
  --resource-group ai-agent-dev-rg \
  --template-file infra/main.bicep \
  --parameters infra/params/dev.bicepparam

# For production
az deployment group create \
  --name ai-agent-prod-deployment \
  --resource-group ai-agent-prod-rg \
  --template-file infra/main.bicep \
  --parameters infra/params/prod.bicepparam
```

#### 5. Retrieve Outputs

```bash
# Extract all outputs
az deployment group show \
  --name ai-agent-dev-deployment \
  --resource-group ai-agent-dev-rg \
  --query 'properties.outputs' --output json
```

**Key outputs**:
- `containerAppUrl`: FQDN of the deployed agent service
- `appInsightsInstrumentationKey`: For application telemetry
- `keyVaultId`: For secret management
- `cosmosDbAccountEndpoint`: Cosmos DB connection endpoint
- `aiSearchEndpoint`: AI Search service endpoint
- `storageAccountId`: Blob Storage for documents

### Rollback

If deployment fails, delete the resource group and retry:

```bash
# This removes all deployed resources
az group delete \
  --name ai-agent-dev-rg \
  --yes --no-wait
```

## Resource Naming

Resources follow a naming convention derived from parameters:

| Resource Type | Naming Scheme | Example |
|---------------|---------------|---------|
| Container App | `{projectName}-{env}-agent` | `ai-agent-dev-agent` |
| Container Env | `{projectName}-{env}-env` | `ai-agent-dev-env` |
| Key Vault | `{projectName shrunk}kv` | `aiagentdevkv` (24 char limit) |
| Storage Account | `{projectName shrunk}storage` | `aiagentdevstorage` (24 char limit) |
| Cosmos DB | `{projectName}-{env}-cosmos` | `ai-agent-dev-cosmos` |
| AI Search | `{projectName}-{env}-search` | `ai-agent-dev-search` |
| App Insights | `{projectName}-{env}-appinsights` | `ai-agent-dev-appinsights` |
| Log Analytics | `{projectName}-{env}-logs` | `ai-agent-dev-logs` |

## Security Considerations

### Managed Identity
- All services use system-assigned or user-assigned managed identities
- No connection strings or API keys stored in code
- RBAC roles grant least-privilege access

### Key Vault
- All secrets (API keys, connection strings) stored in Key Vault
- Managed identity has `get` and `list` permissions only
- Enable purge protection in production

### Network Security
- Network ACLs default to Allow (adjust after deployment if needed)
- Public network access enabled for initial setup (restrict in production)
- Consider private endpoints for production deployments

### Data Protection
- Blob Storage: Lifecycle policies archive old data
- Cosmos DB: TTL-based conversation cleanup (30 days default)
- Encryption: Azure-managed keys by default (use customer-managed keys in production)

## Cost Optimization

### Environment-Specific Tuning

**Development** (`dev.bicepparam`):
- Container Apps: 1 min replica, 3 max replicas
- AI Search: Basic SKU (1 partition, 1 replica)
- Storage: Standard LRS
- Cosmos DB: 400 RU/s per collection (shared throughput)
- Log Analytics: 30-day retention

**Production** (`prod.bicepparam`):
- Container Apps: Auto-scale 1-10 replicas
- AI Search: Standard SKU (for production workloads)
- Storage: Standard LRS with lifecycle policies
- Cosmos DB: Consider dedicated throughput for conversations
- Log Analytics: 30-day retention (extend if needed for compliance)

### Cost Reduction Ideas
1. **Shared Cosmos DB**: Multiple agents can share collections with partition keys
2. **Storage Lifecycle**: Archive documents after 90 days to cool tier
3. **Search Index Optimization**: Use compressed indexes for vector embeddings
4. **App Insights Sampling**: Enable 10-50% sampling in production
5. **Reserved Instances**: Use 1-year/3-year reservations for consistent workloads

## Monitoring and Support

### Application Insights Dashboard
After deployment, create dashboards in Azure Portal:
```
Application Insights → Workbooks → Create
→ Add metrics for: requests, failures, response time, AI-specific traces
```

### Log Analytics Queries
```kusto
// Agent request rate
AppTraces | where severityLevel == 1 | summarize count() by bin(timestamp, 5m)

// Error trend
AppExceptions | summarize count() by tostring(outerExceptionType) | render barchart
```

### Health Checks
- Container App: `/health` endpoint recommended
- Cosmos DB: Monitor RU consumption per collection
- AI Search: Monitor index query latency
- Application Insights: Monitor 4xx/5xx rates

## Extending the Infrastructure

### Adding a New Data Store
1. Create `modules/data/newservice.bicep`
2. Add module reference in `main.bicep`
3. Define outputs and RBAC role assignments
4. Update parameter files if SKU decisions needed

### Adding a New Service
1. Create module file (e.g., `modules/<tier>/<service>.bicep`)
2. Import in main.bicep with appropriate parameters
3. Add RBAC assignments for managed identity
4. Export outputs needed by other modules

### Custom Networking
For production, add:
```bicep
// Virtual Network
module vnet 'modules/networking/vnet.bicep' = { ... }

// Private Endpoints
module kvPrivateEndpoint 'modules/networking/private-endpoint.bicep' = { ... }
```

## Troubleshooting

### Deployment Fails
1. Check Azure CLI version: `az --version`
2. Verify resource group exists: `az group show -n <resource-group>`
3. Review error in portal: Resource Group → Deployments → Failed deployment
4. Check RBAC: `az role assignment list --assignee <managed-identity-object-id>`

### Resources Not Accessible
1. Verify managed identity principal ID matches RBAC assignments
2. Check Key Vault access policies: `az keyvault show -n <vault-name>`
3. Confirm network ACLs: `az storage account show-connection-string -n <storage-account>`

### Quota Issues
If deployment hits quotas:
1. Check current usage: `az usage list --output table`
2. Request limit increase via Azure Portal
3. Try alternative region if available

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Deploy Infrastructure
on:
  push:
    branches: [main]
    paths: ['infra/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - uses: azure/arm-deploy@v1
        with:
          resourceGroupName: ai-agent-prod-rg
          template: infra/main.bicep
          parameters: infra/params/prod.bicepparam
```

### Azure DevOps Pipeline Example
```yaml
trigger:
  - main
  
pool:
  vmImage: 'ubuntu-latest'

steps:
- task: AzureCLI@2
  inputs:
    azureSubscription: 'Production Subscription'
    scriptType: 'bash'
    scriptLocation: 'inlineScript'
    inlineScript: |
      az deployment group create \
        --name ai-agent-prod-deployment \
        --resource-group ai-agent-prod-rg \
        --template-file infra/main.bicep \
        --parameters infra/params/prod.bicepparam
```

## Best Practices

1. **Version Control**: Keep Bicep files in Git with parameter files
2. **Parameterization**: Use parameter files for environment differences; avoid hardcoding
3. **Modular Design**: Each module should have a single responsibility
4. **Documentation**: Update README when module signatures change
5. **Testing**: Validate templates in dev before production deployment
6. **RBAC**: Use managed identities; never embed connection strings in code
7. **Monitoring**: Enable diagnostics on all services from day one
8. **Cost Tracking**: Tag resources for cost allocation by project/department
9. **Disaster Recovery**: Document backup strategies for Cosmos DB and Storage
10. **Security Reviews**: Audit access policies quarterly

## References

- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview)
- [Azure Well-Architected Framework](https://learn.microsoft.com/azure/architecture/framework/)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Azure AI Search](https://learn.microsoft.com/azure/search/)
- [Cosmos DB Best Practices](https://learn.microsoft.com/azure/cosmos-db/best-practices)
- [Azure Key Vault Best Practices](https://learn.microsoft.com/azure/key-vault/general/best-practices)
