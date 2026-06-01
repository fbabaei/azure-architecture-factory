@description('Deployment location')
param location string

@description('Cosmos DB account name')
param cosmosAccountName string

@description('Database name')
param databaseName string

@description('RU/s throughput for containers')
param throughput int = 400

@description('Principal ID of the managed identity')
param identityPrincipalId string

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
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
    capabilities: []
    enableFreeTier: false
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-02-15-preview' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: { id: databaseName }
    options: {}
  }
}

resource agentTemplatesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'agent_templates'
  properties: {
    resource: {
      id: 'agent_templates'
      partitionKey: { paths: ['/template_id'], kind: 'Hash' }
    }
    options: { throughput: throughput }
  }
}

resource agentSessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'agent_sessions'
  properties: {
    resource: {
      id: 'agent_sessions'
      partitionKey: { paths: ['/project_id'], kind: 'Hash' }
      defaultTtl: 86400
    }
    options: { throughput: throughput }
  }
}

resource projectContextsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'project_contexts'
  properties: {
    resource: {
      id: 'project_contexts'
      partitionKey: { paths: ['/project_id'], kind: 'Hash' }
    }
    options: { throughput: throughput }
  }
}

resource evalTracesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'eval_traces'
  properties: {
    resource: {
      id: 'eval_traces'
      partitionKey: { paths: ['/agent_name'], kind: 'Hash' }
      defaultTtl: 2592000
    }
    options: { throughput: throughput }
  }
}

// Cosmos DB Built-in Data Contributor — roleDefinitionId is a fixed GUID for this built-in
resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, identityPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: identityPrincipalId
    scope: cosmosAccount.id
  }
}

output endpoint string = cosmosAccount.properties.documentEndpoint
output accountId string = cosmosAccount.id
