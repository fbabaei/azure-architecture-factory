// Cosmos DB Module
// NoSQL database for operational data, agent state management, and conversation history

param location string
param accountName string
param principalId string
param tags object = {}

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
      maxIntervalInSeconds: 5
      maxStalenessPrefix: 100
    }
    networkAclBypass: 'AzureServices'
    publicNetworkAccess: 'Enabled'
    enableFreeTier: false
  }
}

// Primary database for agent state
resource agentDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDbAccount
  name: 'agent-db'
  properties: {
    resource: {
      id: 'agent-db'
    }
  }
}

// Collection for conversation history
resource conversationContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: agentDatabase
  name: 'conversations'
  properties: {
    resource: {
      id: 'conversations'
      partitionKey: {
        paths: ['/conversationId']
        kind: 'Hash'
      }
      defaultTtl: 2592000 // 30 days
      indexingPolicy: {
        indexingMode: 'Consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/_etag/?'
          }
        ]
      }
    }
    options: {
      throughput: 400
    }
  }
}

// Collection for agent state
resource stateContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: agentDatabase
  name: 'state'
  properties: {
    resource: {
      id: 'state'
      partitionKey: {
        paths: ['/agentId']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'Consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/_etag/?'
          }
        ]
      }
    }
    options: {
      throughput: 400
    }
  }
}

// RBAC: Assign Cosmos DB Built-in Data Contributor role to managed identity
resource cosmosRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmosDbAccount.id, principalId, '00000000-0000-0000-0000-000000000002')
  scope: cosmosDbAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00000000-0000-0000-0000-000000000002') // Cosmos DB Built-in Data Contributor
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output accountId string = cosmosDbAccount.id
output accountEndpoint string = cosmosDbAccount.properties.documentEndpoint
output accountName string = cosmosDbAccount.name
output databaseName string = agentDatabase.name
