// Azure AI Search service. Local (key) auth is disabled — runtime queries and
// indexer/pipeline management use Entra ID + Search data-plane RBAC. The
// service carries a system-assigned identity so the indexer can read blobs and
// call Azure OpenAI for embeddings without keys.
param name string
param location string
param tags object = {}

@allowed([
  'free'
  'basic'
  'standard'
  'standard2'
  'standard3'
])
param skuName string = 'standard'

@description('Disable local (API key) auth. Must stay true per the security audit.')
param disableLocalAuth bool = true

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    disableLocalAuth: disableLocalAuth
    semanticSearch: 'standard'
    publicNetworkAccess: 'enabled'
  }
}

output id string = search.id
output name string = search.name
output endpoint string = 'https://${search.name}.search.windows.net'
output principalId string = search.identity.principalId
