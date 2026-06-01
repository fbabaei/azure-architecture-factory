metadata description = 'OrderManagement Platform - Main Infrastructure Orchestrator'
metadata author = 'Azure Architecture'

param projectName string
param environment string
param location string
param deploymentDate string = utcNow('u')

// Derived values
var resourceGroupName = '${projectName}-${environment}-rg'

// Tag for all resources
var commonTags = {
  project: projectName
  environment: environment
  deploymentDate: deploymentDate
  owner: 'OrderManagement'
}

// Module: Networking
module networking './modules/networking/vnet.bicep' = {
  name: 'networkingDeploy'
  params: {
    location: location
    projectName: projectName
    environment: environment
    commonTags: commonTags
  }
}

// Module: Security (Key Vault, Managed Identities)
module security './modules/security/keyvault.bicep' = {
  name: 'securityDeploy'
  params: {
    location: location
    projectName: projectName
    environment: environment
    commonTags: commonTags
  }
}

// Module: Monitoring (App Insights, Log Analytics)
module monitoring './modules/monitoring/appinsights.bicep' = {
  name: 'monitoringDeploy'
  params: {
    location: location
    projectName: projectName
    environment: environment
    commonTags: commonTags
  }
}

// Module: Data (Cosmos DB, SQL Database, Service Bus)
module data './modules/data/cosmosdb.bicep' = {
  name: 'dataDeploy'
  params: {
    location: location
    projectName: projectName
    commonTags: commonTags
  }
}

// Module: Compute (Container Apps, ACR)
module compute './modules/compute/containerappenv.bicep' = {
  name: 'computeDeploy'
  params: {
    location: location
    projectName: projectName
    environment: environment
    commonTags: commonTags
    appInsightsInstrumentationKey: monitoring.outputs.appInsightsInstrumentationKey
  }
}

// Outputs
output resourceGroupName string = resourceGroupName
output containerAppEnvironmentId string = compute.outputs.containerAppEnvironmentId
output cosmosDbEndpoint string = data.outputs.cosmosDbEndpoint
output serviceBusNamespace string = data.outputs.serviceBusNamespace
output keyVaultName string = security.outputs.keyVaultName
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
