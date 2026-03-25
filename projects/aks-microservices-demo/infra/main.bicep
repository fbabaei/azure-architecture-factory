targetScope = 'resourceGroup'

@description('Deployment location')
param location string = resourceGroup().location

@description('Environment name: dev/test/prod')
@allowed([
  'dev'
  'test'
  'prod'
])
param environment string = 'dev'

@description('AKS cluster name')
param aksClusterName string = 'aks-micro-${environment}'

@description('AKS DNS prefix')
param dnsPrefix string = 'aksmicro${environment}'

@description('Azure Container Registry name (globally unique)')
param acrName string = 'acrmicro${uniqueString(subscription().subscriptionId, resourceGroup().id, environment)}'

@description('Key Vault name (globally unique)')
param keyVaultName string = 'kvmicro${uniqueString(subscription().subscriptionId, resourceGroup().id, environment)}'

@description('Log Analytics workspace name')
param logAnalyticsWorkspaceName string = 'law-aks-micro-${environment}'

module logAnalytics './modules/monitoring/log-analytics.bicep' = {
  name: 'logAnalyticsDeploy'
  params: {
    location: location
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
  }
}

module acr './modules/compute/acr.bicep' = {
  name: 'acrDeploy'
  params: {
    location: location
    acrName: acrName
  }
}

module keyVault './modules/security/keyvault.bicep' = {
  name: 'keyVaultDeploy'
  params: {
    location: location
    keyVaultName: keyVaultName
  }
}

module aks './modules/compute/aks.bicep' = {
  name: 'aksDeploy'
  params: {
    location: location
    aksClusterName: aksClusterName
    dnsPrefix: dnsPrefix
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    acrName: acr.outputs.acrName
  }
}

output aksName string = aks.outputs.aksName
output acrLoginServer string = acr.outputs.acrLoginServer
output keyVaultName string = keyVault.outputs.keyVaultName
output logAnalyticsWorkspaceName string = logAnalytics.outputs.workspaceName
