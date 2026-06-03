// Cosmos DB (SQL API) for chat history and SharePoint sync state. Entra-only:
// local key auth and key-based metadata writes are disabled — the apps use the
// Cosmos SQL built-in data-plane role (assigned in modules/rbac.bicep).
param accountName string
param location string
param tags object = {}

param databaseName string = 'casewright'
param historyContainerName string = 'chat-history'
param syncStateContainerName string = 'sync-state'

@description('Disable local (key) auth. Must stay true per the security audit.')
param disableLocalAuth bool = true

resource account 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: disableLocalAuth
    disableKeyBasedMetadataWriteAccess: true
    enableAutomaticFailover: false
    minimalTlsVersion: 'Tls12'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-11-15' = {
  parent: account
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Hierarchical partition key: tenant -> user -> conversation. Keeps a single
// conversation's turns co-located for cheap ORDER BY created_at reads.
resource historyContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: historyContainerName
  properties: {
    resource: {
      id: historyContainerName
      partitionKey: {
        paths: [
          '/tenantId'
          '/userId'
          '/conversationId'
        ]
        kind: 'MultiHash'
        version: 2
      }
      defaultTtl: -1
    }
  }
}

resource syncStateContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-11-15' = {
  parent: database
  name: syncStateContainerName
  properties: {
    resource: {
      id: syncStateContainerName
      partitionKey: {
        paths: [
          '/tenantId'
        ]
        kind: 'Hash'
      }
    }
  }
}

output id string = account.id
output name string = account.name
output endpoint string = account.properties.documentEndpoint
output databaseName string = database.name
output historyContainerName string = historyContainer.name
output syncStateContainerName string = syncStateContainer.name
