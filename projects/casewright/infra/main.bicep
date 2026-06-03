// Casewright — resource-group-scoped deployment.
// RAG case-knowledge assistant: Container Apps (API + worker), a scheduler
// Function App, AI Search, Azure OpenAI, Cosmos DB, Service Bus, Storage.
// Managed-identity-first; no account keys (see modules/rbac.bicep).
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(16)
@description('Short base name used to derive resource names.')
param baseName string = 'casewright'

@description('Deployment environment (dev/test/prod) — used in tags + naming.')
param environmentName string = 'dev'

param location string = resourceGroup().location

@description('Container image for the API service (e.g. <acr>.azurecr.io/casewright-api:latest).')
param apiImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Container image for the worker service.')
param workerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Entra tenant for Microsoft Graph (SharePoint) app-only auth.')
param graphTenantId string = ''

@description('App registration client id for Microsoft Graph (SharePoint).')
param graphClientId string = ''

@description('NCRONTAB schedule for the SharePoint sync timer.')
param sharePointSyncSchedule string = '0 0 */6 * * *'

@description('Tenant id stamped on scheduler-initiated sync requests.')
param syncDefaultTenantId string = ''

@description('Embedding vector dimensions — must match the retrieval index.')
param embeddingDimensions int = 3072

var tags = {
  application: 'casewright'
  environment: environmentName
}

var suffix = uniqueString(resourceGroup().id, baseName, environmentName)
var shortSuffix = take(suffix, 8)

// Deterministic resource names.
var names = {
  apiIdentity: '${baseName}-api-id-${shortSuffix}'
  workerIdentity: '${baseName}-worker-id-${shortSuffix}'
  schedulerIdentity: '${baseName}-sched-id-${shortSuffix}'
  logAnalytics: '${baseName}-log-${shortSuffix}'
  appInsights: '${baseName}-appi-${shortSuffix}'
  keyVault: take('${baseName}kv${shortSuffix}', 24)
  storage: take('${baseName}st${shortSuffix}', 24)
  functionStorage: take('${baseName}fn${shortSuffix}', 24)
  registry: take('${baseName}acr${shortSuffix}', 50)
  search: '${baseName}-search-${shortSuffix}'
  openai: '${baseName}-openai-${shortSuffix}'
  cosmos: '${baseName}-cosmos-${shortSuffix}'
  serviceBus: '${baseName}-sb-${shortSuffix}'
  containerEnv: '${baseName}-cae-${shortSuffix}'
  apiApp: 'casewright-api'
  workerApp: 'casewright-worker'
  functionPlan: '${baseName}-fc-${shortSuffix}'
  functionApp: '${baseName}-scheduler-${shortSuffix}'
}

// ---- Identities (one per workload) ----
module apiIdentity 'modules/identity.bicep' = {
  name: 'apiIdentity'
  params: {
    name: names.apiIdentity
    location: location
    tags: tags
  }
}

module workerIdentity 'modules/identity.bicep' = {
  name: 'workerIdentity'
  params: {
    name: names.workerIdentity
    location: location
    tags: tags
  }
}

module schedulerIdentity 'modules/identity.bicep' = {
  name: 'schedulerIdentity'
  params: {
    name: names.schedulerIdentity
    location: location
    tags: tags
  }
}

// ---- Observability ----
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: names.logAnalytics
    appInsightsName: names.appInsights
    location: location
    tags: tags
  }
}

// ---- Stateful + supporting resources ----
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVault'
  params: {
    name: names.keyVault
    location: location
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    name: names.storage
    location: location
    tags: tags
  }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  params: {
    name: names.registry
    location: location
    tags: tags
  }
}

module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    name: names.search
    location: location
    tags: tags
  }
}

module openai 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    name: names.openai
    location: location
    tags: tags
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    accountName: names.cosmos
    location: location
    tags: tags
  }
}

module serviceBus 'modules/servicebus.bicep' = {
  name: 'serviceBus'
  params: {
    namespaceName: names.serviceBus
    location: location
    tags: tags
  }
}

// ---- Container Apps environment ----
resource logAnalyticsRef 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: names.logAnalytics
}

module containerEnv 'modules/containerenv.bicep' = {
  name: 'containerEnv'
  params: {
    name: names.containerEnv
    location: location
    tags: tags
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: logAnalyticsRef.listKeys().primarySharedKey
  }
}

// ---- Shared app settings (Casewright Settings env vars) ----
var coreEnvVars = [
  {
    name: 'SEARCHSERVICE_ENDPOINT'
    value: search.outputs.endpoint
  }
  {
    name: 'SEARCH_INDEX_NAME'
    value: '${baseName}-index'
  }
  {
    name: 'AZURE_OPENAI_ENDPOINT'
    value: openai.outputs.endpoint
  }
  {
    name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
    value: openai.outputs.chatDeploymentName
  }
  {
    name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
    value: openai.outputs.embeddingDeploymentName
  }
  {
    name: 'AZURE_OPENAI_EMBEDDING_DIMENSIONS'
    value: string(embeddingDimensions)
  }
  {
    name: 'BLOBSTORAGE_ACCOUNT_URL'
    value: storage.outputs.blobEndpoint
  }
  {
    name: 'INGESTION_CONTAINER'
    value: 'ingestion'
  }
  {
    name: 'KNOWLEDGE_STORE_CONTAINER'
    value: 'knowledge-store'
  }
  {
    name: 'COSMOS_ENDPOINT'
    value: cosmos.outputs.endpoint
  }
  {
    name: 'COSMOS_DATABASE'
    value: cosmos.outputs.databaseName
  }
  {
    name: 'COSMOS_HISTORY_CONTAINER'
    value: cosmos.outputs.historyContainerName
  }
  {
    name: 'COSMOS_SYNC_STATE_CONTAINER'
    value: cosmos.outputs.syncStateContainerName
  }
  {
    name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
    value: serviceBus.outputs.fqdn
  }
  {
    name: 'SERVICEBUS_QUEUE_NAME'
    value: serviceBus.outputs.queueName
  }
  {
    name: 'GRAPH_TENANT_ID'
    value: graphTenantId
  }
  {
    name: 'GRAPH_CLIENT_ID'
    value: graphClientId
  }
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: monitoring.outputs.appInsightsConnectionString
  }
]

var apiEnvVars = concat(coreEnvVars, [
  {
    name: 'AZURE_CLIENT_ID'
    value: apiIdentity.outputs.clientId
  }
])

var workerEnvVars = concat(coreEnvVars, [
  {
    name: 'AZURE_CLIENT_ID'
    value: workerIdentity.outputs.clientId
  }
])

// ---- Container Apps ----
module apiApp 'modules/containerapp.bicep' = {
  name: 'apiApp'
  params: {
    name: names.apiApp
    location: location
    tags: tags
    environmentId: containerEnv.outputs.id
    identityId: apiIdentity.outputs.id
    registryLoginServer: registry.outputs.loginServer
    image: apiImage
    externalIngress: true
    targetPort: 8000
    minReplicas: 1
    maxReplicas: 3
    envVars: apiEnvVars
    serviceName: 'casewright-api'
  }
}

module workerApp 'modules/containerapp.bicep' = {
  name: 'workerApp'
  params: {
    name: names.workerApp
    location: location
    tags: tags
    environmentId: containerEnv.outputs.id
    identityId: workerIdentity.outputs.id
    registryLoginServer: registry.outputs.loginServer
    image: workerImage
    externalIngress: false
    minReplicas: 1
    maxReplicas: 5
    envVars: workerEnvVars
    command: ['python', '-m', 'casewright.worker.sb_worker']
    serviceName: 'casewright-worker'
  }
}

// ---- Scheduler Function App ----
module functionApp 'modules/functionapp.bicep' = {
  name: 'functionApp'
  params: {
    name: names.functionApp
    location: location
    tags: tags
    planName: names.functionPlan
    storageAccountName: names.functionStorage
    identityId: schedulerIdentity.outputs.id
    identityClientId: schedulerIdentity.outputs.clientId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    serviceName: 'casewright-scheduler'
    appSettings: [
      {
        name: 'SHAREPOINT_SYNC_SCHEDULE'
        value: sharePointSyncSchedule
      }
      {
        name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
        value: serviceBus.outputs.fqdn
      }
      {
        name: 'SERVICEBUS_QUEUE_NAME'
        value: serviceBus.outputs.queueName
      }
      {
        name: 'GRAPH_TENANT_ID'
        value: graphTenantId
      }
      {
        name: 'GRAPH_CLIENT_ID'
        value: graphClientId
      }
      {
        name: 'SYNC_DEFAULT_TENANT_ID'
        value: syncDefaultTenantId
      }
    ]
  }
}

// ---- Data-plane RBAC (must match docs/security/security-audit.json) ----
module rbac 'modules/rbac.bicep' = {
  name: 'rbac'
  params: {
    searchServiceName: search.outputs.name
    storageAccountName: storage.outputs.name
    openAiName: openai.outputs.name
    serviceBusNamespaceName: serviceBus.outputs.name
    cosmosAccountName: cosmos.outputs.name
    registryName: registry.outputs.name
    apiPrincipalId: apiIdentity.outputs.principalId
    workerPrincipalId: workerIdentity.outputs.principalId
    schedulerPrincipalId: schedulerIdentity.outputs.principalId
    searchPrincipalId: search.outputs.principalId
  }
}

// ---- Outputs ----
output apiFqdn string = apiApp.outputs.fqdn
output registryLoginServer string = registry.outputs.loginServer
output searchEndpoint string = search.outputs.endpoint
output openAiEndpoint string = openai.outputs.endpoint
output cosmosEndpoint string = cosmos.outputs.endpoint
output serviceBusFqdn string = serviceBus.outputs.fqdn
output storageBlobEndpoint string = storage.outputs.blobEndpoint
output keyVaultUri string = keyVault.outputs.uri
output functionAppName string = functionApp.outputs.name
output apiIdentityClientId string = apiIdentity.outputs.clientId
output workerIdentityClientId string = workerIdentity.outputs.clientId
output schedulerIdentityClientId string = schedulerIdentity.outputs.clientId
