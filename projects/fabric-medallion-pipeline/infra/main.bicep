// ======================================================================
// Fabric Medallion Pipeline — Main Bicep Orchestrator
// Deploys: ADLS Gen2, Container Apps Environment, Key Vault,
//          Application Insights, Log Analytics, Managed Identity,
//          Container Registry
// ======================================================================

targetScope = 'resourceGroup'

@description('Deployment environment name')
@allowed(['dev', 'test', 'prod'])
param environmentName string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Unique suffix to avoid naming collisions')
param resourceSuffix string = uniqueString(resourceGroup().id)

@description('ADLS Gen2 storage account name (max 24 chars, lowercase, alphanumeric)')
param storageAccountName string = 'medallion${take(resourceSuffix, 8)}'

@description('Container Apps environment name')
param containerAppEnvName string = 'cae-medallion-${environmentName}'

@description('Key Vault name')
param keyVaultName string = 'kv-medallion-${take(resourceSuffix, 8)}'

@description('Application Insights name')
param appInsightsName string = 'appi-medallion-${environmentName}'

@description('Log Analytics Workspace name')
param logAnalyticsName string = 'law-medallion-${environmentName}'

@description('Managed Identity name')
param managedIdentityName string = 'mi-medallion-${environmentName}'

@description('Container Registry name')
param containerRegistryName string = 'acrmedallion${take(resourceSuffix, 8)}'

// ──────────────────────────────────────────────
// Modules
// ──────────────────────────────────────────────

module managedIdentity 'modules/security/managed-identity.bicep' = {
  name: 'managed-identity'
  params: {
    name: managedIdentityName
    location: location
    tags: { environment: environmentName, project: 'fabric-medallion-pipeline' }
  }
}

module logAnalytics 'modules/monitoring/log-analytics.bicep' = {
  name: 'log-analytics'
  params: {
    name: logAnalyticsName
    location: location
    tags: { environment: environmentName, project: 'fabric-medallion-pipeline' }
  }
}

module appInsights 'modules/monitoring/appinsights.bicep' = {
  name: 'app-insights'
  params: {
    name: appInsightsName
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: { environment: environmentName, project: 'fabric-medallion-pipeline' }
  }
}

module storage 'modules/storage/adls.bicep' = {
  name: 'adls-storage'
  params: {
    name: storageAccountName
    location: location
    managedIdentityPrincipalId: managedIdentity.outputs.principalId
    tags: { environment: environmentName, project: 'fabric-medallion-pipeline' }
  }
}

module keyVault 'modules/security/keyvault.bicep' = {
  name: 'key-vault'
  params: {
    name: keyVaultName
    location: location
    managedIdentityPrincipalId: managedIdentity.outputs.principalId
    tags: { environment: environmentName, project: 'fabric-medallion-pipeline' }
  }
}

module containerRegistry 'modules/compute/container-registry.bicep' = {
  name: 'container-registry'
  params: {
    name: containerRegistryName
    location: location
    managedIdentityPrincipalId: managedIdentity.outputs.principalId
    tags: { environment: environmentName, project: 'fabric-medallion-pipeline' }
  }
}

module containerAppEnv 'modules/compute/containerappenv.bicep' = {
  name: 'container-app-env'
  params: {
    name: containerAppEnvName
    location: location
    logAnalyticsCustomerId: logAnalytics.outputs.customerId
    logAnalyticsSharedKey: logAnalytics.outputs.primarySharedKey
    tags: { environment: environmentName, project: 'fabric-medallion-pipeline' }
  }
}

// ──────────────────────────────────────────────
// Outputs
// ──────────────────────────────────────────────

output storageAccountName string = storage.outputs.storageAccountName
output storageAccountId string = storage.outputs.storageAccountId
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output appInsightsConnectionString string = appInsights.outputs.connectionString
output logAnalyticsWorkspaceId string = logAnalytics.outputs.workspaceId
output managedIdentityClientId string = managedIdentity.outputs.clientId
output containerAppEnvironmentId string = containerAppEnv.outputs.environmentId
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
