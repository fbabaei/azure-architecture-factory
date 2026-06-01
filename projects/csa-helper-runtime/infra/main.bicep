// CSA Helper Runtime — main.bicep
// Hosting layer for the existing csa-helper agent-framework runtime.
// Deploys: Log Analytics, App Insights, ACR (Basic), UAMI, Key Vault,
//          Container Apps Env, Container App; plus a cross-RG role
//          assignment on the EXISTING Azure OpenAI account.

targetScope = 'resourceGroup'

@description('Project slug — used for resource names')
param projectName string = 'csa-helper-runtime'

@description('Deployment environment')
@allowed([ 'dev', 'test', 'prod' ])
param environment string = 'dev'

@description('Azure region for all resources created by this template')
param location string = 'eastus2'

@description('Container image to deploy. Set to <acr-login-server>/csa-helper-runtime:<tag> after the first ACR push.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Name of the EXISTING Azure OpenAI account')
param aoaiAccountName string = 'fbfoundrywestus'

@description('Resource group of the EXISTING Azure OpenAI account')
param aoaiResourceGroupName string = 'rg-fbabaei-2653'

@description('Endpoint URL for the EXISTING Azure OpenAI account (https://<name>.openai.azure.com/). Stored as a Key Vault secret.')
@secure()
param aoaiEndpoint string

@description('AOAI deployment name (plain env var)')
param aoaiDeployment string = 'gpt-4o'

@description('AOAI api-version (plain env var)')
param aoaiApiVersion string = '2024-10-21'

@description('Min replicas (NFR-2 allows 0)')
param minReplicas int = 0
@description('Max replicas (NFR-2)')
param maxReplicas int = 3

var tags = {
  project: projectName
  environment: environment
  managedBy: 'azure-architecture-factory'
}

// Stable, lowercase token derived from the resource group id — used to make
// globally unique names (ACR + Key Vault) deterministic per RG.
var nameToken = toLower(uniqueString(resourceGroup().id, projectName))

var lawName    = '${projectName}-${environment}-law'
var aiName     = '${projectName}-${environment}-ai'
var uamiName   = '${projectName}-${environment}-id'
var caeName    = '${projectName}-${environment}-cae'
var cappName   = projectName
var acrName    = toLower(replace('${projectName}${nameToken}', '-', ''))
var kvName     = take(toLower(replace('${projectName}${nameToken}kv', '-', '')), 24)

module law 'modules/monitoring/log-analytics.bicep' = {
  name: 'log-analytics'
  params: {
    location: location
    workspaceName: lawName
    retentionInDays: 30
    tags: tags
  }
}

module appInsights 'modules/monitoring/appinsights.bicep' = {
  name: 'app-insights'
  params: {
    location: location
    appInsightsName: aiName
    workspaceId: law.outputs.id
    tags: tags
  }
}

module uami 'modules/identity/managed-identity.bicep' = {
  name: 'uami'
  params: {
    location: location
    identityName: uamiName
    tags: tags
  }
}

module acr 'modules/compute/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    registryName: take(acrName, 50)
    pullPrincipalId: uami.outputs.principalId
    sku: 'Basic'
    tags: tags
  }
}

module keyVault 'modules/security/keyvault.bicep' = {
  name: 'key-vault'
  params: {
    location: location
    keyVaultName: kvName
    secretsUserPrincipalId: uami.outputs.principalId
    aoaiEndpoint: aoaiEndpoint
    tags: tags
  }
}

module containerEnv 'modules/compute/containerappenv.bicep' = {
  name: 'container-env'
  params: {
    location: location
    envName: caeName
    workspaceId: law.outputs.id
    tags: tags
  }
}

module containerApp 'modules/compute/containerapp.bicep' = {
  name: 'container-app'
  params: {
    location: location
    containerAppName: cappName
    containerEnvId: containerEnv.outputs.id
    containerImage: containerImage
    managedIdentityId: uami.outputs.id
    acrLoginServer: acr.outputs.loginServer
    appInsightsConnectionString: appInsights.outputs.connectionString
    aoaiEndpointSecretUri: keyVault.outputs.aoaiEndpointSecretUri
    aoaiDeployment: aoaiDeployment
    aoaiApiVersion: aoaiApiVersion
    minReplicas: minReplicas
    maxReplicas: maxReplicas
    tags: tags
  }
}

// Cross-RG role assignment on the EXISTING Azure OpenAI account.
// NOTE: deploying principal needs Owner / User Access Administrator on
// `rg-fbabaei-2653` for this assignment to succeed.
module aoaiRole 'modules/rbac/aoai-role-assignment.bicep' = {
  name: 'aoai-role'
  scope: resourceGroup(aoaiResourceGroupName)
  params: {
    aoaiAccountName: aoaiAccountName
    principalId: uami.outputs.principalId
  }
}

output containerAppFqdn string = containerApp.outputs.fqdn
output containerAppUrl  string = containerApp.outputs.url
output acrLoginServer   string = acr.outputs.loginServer
output keyVaultUri      string = keyVault.outputs.uri
output managedIdentityClientId string = uami.outputs.clientId
output appInsightsConnectionString string = appInsights.outputs.connectionString
