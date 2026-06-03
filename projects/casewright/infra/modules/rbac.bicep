// Central data-plane RBAC — mirrors docs/security/security-audit.json exactly.
// Every hop uses managed identity; no account keys anywhere. Three app
// identities (api/worker/scheduler) + the Search service system identity.
param searchServiceName string
param storageAccountName string
param openAiName string
param serviceBusNamespaceName string
param cosmosAccountName string
param registryName string

param apiPrincipalId string
param workerPrincipalId string
param schedulerPrincipalId string
param searchPrincipalId string

// ---- Built-in role definition IDs ----
var searchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var searchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
var cognitiveServicesOpenAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var serviceBusDataSender = '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
var serviceBusDataReceiver = '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
// Cosmos DB built-in SQL data-plane role: "Cosmos DB Built-in Data Contributor".
var cosmosDataContributorRole = '00000000-0000-0000-0000-000000000002'

// ---- Existing resources (scopes) ----
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}
resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiName
}
resource serviceBus 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' existing = {
  name: serviceBusNamespaceName
}
resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: registryName
}
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

// ---- Search service data plane ----
// api: runtime hybrid query.
resource apiSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, apiPrincipalId, searchIndexDataReader)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataReader)
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// worker: runs indexers + pipeline setup.
resource workerSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, workerPrincipalId, searchServiceContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributor)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---- Storage data plane ----
// worker: writes synced source documents into the ingestion container.
resource workerBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, workerPrincipalId, storageBlobDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// search-service: reads source blobs + writes the knowledge store.
resource searchBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, searchPrincipalId, storageBlobDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource searchBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, searchPrincipalId, storageBlobDataReader)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReader)
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---- Azure OpenAI data plane ----
// api: chat + embedding for retrieval grounding.
resource apiOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openai
  name: guid(openai.id, apiPrincipalId, cognitiveServicesOpenAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUser)
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// search-service: vectorizer + embedding skill.
resource searchOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openai
  name: guid(openai.id, searchPrincipalId, cognitiveServicesOpenAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUser)
    principalId: searchPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---- Service Bus data plane ----
// api + scheduler: enqueue sync requests.
resource apiSbSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: serviceBus
  name: guid(serviceBus.id, apiPrincipalId, serviceBusDataSender)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceBusDataSender)
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource schedulerSbSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: serviceBus
  name: guid(serviceBus.id, schedulerPrincipalId, serviceBusDataSender)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceBusDataSender)
    principalId: schedulerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// worker: consume sync requests.
resource workerSbReceiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: serviceBus
  name: guid(serviceBus.id, workerPrincipalId, serviceBusDataReceiver)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceBusDataReceiver)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---- ACR pull (image hosting for api + worker) ----
resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, apiPrincipalId, acrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workerAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, workerPrincipalId, acrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
    principalId: workerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---- Cosmos DB SQL data plane (built-in data contributor) ----
// api + worker read/write chat history and sync state without keys.
resource apiCosmosData 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmos
  name: guid(cosmos.id, apiPrincipalId, cosmosDataContributorRole)
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributorRole}'
    principalId: apiPrincipalId
    scope: cosmos.id
  }
}

resource workerCosmosData 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = {
  parent: cosmos
  name: guid(cosmos.id, workerPrincipalId, cosmosDataContributorRole)
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributorRole}'
    principalId: workerPrincipalId
    scope: cosmos.id
  }
}
