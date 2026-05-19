// Main Bicep file for Azure AI Foundry Agent Application
// Orchestrates deployment of compute, AI, data, security, and monitoring resources

param environment string = 'dev'
param location string = resourceGroup().location
param projectName string = 'ai-agent'
param containerImageUri string = 'mcr.microsoft.com/azure-app-service/defaultsite:latest' // Replace with your container image
param containerPort int = 8000

// Derived parameters
var appName = '${projectName}-${environment}'
var containerAppName = '${appName}-agent'
var containerEnvName = '${appName}-env'
var keyVaultName = substring('${replace(appName, '-', '')}kv', 0, min(24, length('${replace(appName, '-', '')}kv')))
var storageAccountName = substring(replace('${appName}storage', '-', ''), 0, min(24, length(replace('${appName}storage', '-', ''))))
var cosmosDbAccountName = '${appName}-cosmos'
var aiSearchServiceName = '${appName}-search'
var appInsightsName = '${appName}-appinsights'
var logAnalyticsWorkspaceName = '${appName}-logs'

// Managed Identity for Container App
module managedIdentity 'modules/security/managed-identity.bicep' = {
  name: 'managedIdentity'
  params: {
    location: location
    identityName: '${appName}-identity'
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// Key Vault for secrets
module keyVault 'modules/security/keyvault.bicep' = {
  name: 'keyVault'
  params: {
    location: location
    keyVaultName: keyVaultName
    tenantId: subscription().tenantId
    principalId: managedIdentity.outputs.principalId
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// Log Analytics Workspace
module logAnalytics 'modules/monitoring/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    location: location
    workspaceName: logAnalyticsWorkspaceName
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// Application Insights
module appInsights 'modules/monitoring/appinsights.bicep' = {
  name: 'appInsights'
  params: {
    location: location
    appInsightsName: appInsightsName
    workspaceId: logAnalytics.outputs.workspaceId
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// Blob Storage
module storage 'modules/data/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageAccountName: storageAccountName
    principalId: managedIdentity.outputs.principalId
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// Cosmos DB
module cosmosDb 'modules/data/cosmosdb.bicep' = {
  name: 'cosmosDb'
  params: {
    location: location
    accountName: cosmosDbAccountName
    principalId: managedIdentity.outputs.principalId
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// Azure AI Search
module aiSearch 'modules/ai/search.bicep' = {
  name: 'aiSearch'
  params: {
    location: location
    searchServiceName: aiSearchServiceName
    sku: environment == 'prod' ? 'standard' : 'basic'
    principalId: managedIdentity.outputs.principalId
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// Container Apps Environment and Agent Service
module containerApps 'modules/compute/containerappenv.bicep' = {
  name: 'containerApps'
  params: {
    location: location
    containerEnvName: containerEnvName
    containerAppName: containerAppName
    containerImageUri: containerImageUri
    containerPort: containerPort
    appInsightsInstrumentationKey: appInsights.outputs.instrumentationKey
    managedIdentityId: managedIdentity.outputs.id
    keyVaultUrl: keyVault.outputs.vaultUri
    workspaceId: logAnalytics.outputs.workspaceId
    environment: environment
    projectName: projectName
    tags: {
      environment: environment
      project: projectName
    }
  }
}

// RBAC: Grant Container App access to Key Vault
resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = {
  name: '${keyVault.name}/add'
  properties: {
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: managedIdentity.outputs.principalId
        permissions: {
          secrets: ['get', 'list']
          certificates: ['get', 'list']
        }
      }
    ]
  }
}

// Outputs
output containerAppUrl string = containerApps.outputs.containerAppUrl
output keyVaultId string = keyVault.outputs.keyVaultId
output storageAccountId string = storage.outputs.storageAccountId
output cosmosDbAccountEndpoint string = cosmosDb.outputs.accountEndpoint
output aiSearchEndpoint string = aiSearch.outputs.searchEndpoint
output appInsightsInstrumentationKey string = appInsights.outputs.instrumentationKey
output managedIdentityId string = managedIdentity.outputs.id
output logAnalyticsWorkspaceId string = logAnalytics.outputs.workspaceId
