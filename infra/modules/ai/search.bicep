// Azure AI Search Module
// Vector and hybrid search capabilities for semantic understanding and RAG

param location string
param searchServiceName string
param sku string = 'basic' // basic or standard
param principalId string
param tags object = {}

resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
  }
}

// RBAC: Assign Search Index Data Contributor role to managed identity
resource searchRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, principalId, '8ebe5a00-0100-4202-9e9e-39a5b4b5a364')
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-0100-4202-9e9e-39a5b4b5a364') // Search Index Data Contributor
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
output searchServiceId string = searchService.id
output searchServiceName string = searchService.name
