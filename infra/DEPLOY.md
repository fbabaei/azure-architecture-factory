# Infrastructure as Code Quick Reference

## Quick Deploy (Development)

```bash
# Create resource group
az group create --name ai-agent-dev-rg --location eastus

# Validate template
az deployment group validate \
  --resource-group ai-agent-dev-rg \
  --template-file main.bicep \
  --parameters params/dev.bicepparam

# Deploy to Azure
az deployment group create \
  --name ai-agent-dev \
  --resource-group ai-agent-dev-rg \
  --template-file main.bicep \
  --parameters params/dev.bicepparam

# Get outputs
az deployment group show \
  --name ai-agent-dev \
  --resource-group ai-agent-dev-rg \
  --query 'properties.outputs' -o json
```

## Quick Deploy (Production)

```bash
# Create resource group
az group create --name ai-agent-prod-rg --location eastus

# Edit production parameters
code params/prod.bicepparam

# Validate and deploy
az deployment group create \
  --name ai-agent-prod \
  --resource-group ai-agent-prod-rg \
  --template-file main.bicep \
  --parameters params/prod.bicepparam
```

## What Gets Deployed

| Service | Dev | Prod | Purpose |
|---------|-----|------|---------|
| Container Apps | 1-3 replicas | 1-10 replicas | Run agent service |
| AI Search | Basic | Standard | Vector/hybrid search |
| Blob Storage | Hot/LRS | Hot/LRS | Document storage |
| Cosmos DB | 400 RU/s | 800+ RU/s | State & conversations |
| Key Vault | Standard | Standard | Secrets & API keys |
| App Insights | Enabled | Enabled | Monitoring & traces |
| Managed Identity | User-assigned | User-assigned | Keyless auth |

## Key Outputs

After deployment, use these values to configure your agent:

```json
{
  "containerAppUrl": "https://ai-agent-dev-agent.xxx.azurecontainerapps.io",
  "appInsightsInstrumentationKey": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "keyVaultId": "/subscriptions/.../resourceGroups/.../providers/Microsoft.KeyVault/vaults/...",
  "cosmosDbAccountEndpoint": "https://ai-agent-dev-cosmos.documents.azure.com:443/",
  "aiSearchEndpoint": "https://ai-agent-dev-search.search.windows.net",
  "storageAccountId": "/subscriptions/.../resourceGroups/.../providers/Microsoft.Storage/storageAccounts/..."
}
```

## Useful Commands

```bash
# List resources deployed
az resource list --resource-group ai-agent-dev-rg --output table

# Get Container App FQDN
az containerapp show -n ai-agent-dev-agent \
  -g ai-agent-dev-rg \
  --query 'properties.configuration.ingress.fqdn'

# Get Cosmos DB connection string (via app settings)
# Store in Key Vault, retrieve with managed identity

# View logs from Container App
az containerapp logs show -n ai-agent-dev-agent -g ai-agent-dev-rg

# Update container image after deployment
az containerapp update \
  -n ai-agent-dev-agent \
  -g ai-agent-dev-rg \
  --image <newimage>:tag

# Delete deployment (when no longer needed)
az group delete --name ai-agent-dev-rg --yes
```

## Environment Variables

These are automatically set in the Container App:

```bash
APPLICATIONINSIGHTS_CONNECTION_STRING=<from appinsights module>
KEY_VAULT_URL=<from keyvault module>
ENVIRONMENT=dev  # or test, prod
PROJECT_NAME=ai-agent
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Deployment fails | Run `validate` first, check error message in portal |
| Can't access resources | Verify managed identity RBAC assignments |
| High costs | Check Cosmos DB RU/s and AI Search SKU |
| Slow queries | Review Cosmos DB indexes and AI Search query time |
| No logs in App Insights | Verify connection string in container app env vars |

See `README.md` for detailed documentation.
