// Storage account for ingestion source documents and the AI Search knowledge
// store. Shared-key access is disabled — every reader/writer uses managed
// identity + Storage Blob Data RBAC (see modules/rbac.bicep).
param name string
param location string
param tags object = {}

@description('Allow shared key (account key) access. Must stay false per the security audit.')
param allowSharedKeyAccess bool = false

@description('Blob containers to create.')
param containerNames array = [
  'ingestion'
  'knowledge-store'
]

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowSharedKeyAccess: allowSharedKeyAccess
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for c in containerNames: {
    parent: blobService
    name: c
    properties: {
      publicAccess: 'None'
    }
  }
]

output id string = storage.id
output name string = storage.name
output blobEndpoint string = storage.properties.primaryEndpoints.blob
