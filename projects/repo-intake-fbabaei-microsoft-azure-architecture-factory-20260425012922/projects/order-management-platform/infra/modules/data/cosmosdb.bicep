metadata description = 'Azure Cosmos DB for OrderManagement Platform'

param location string
param projectName string
param commonTags object

var uniqueSuffix = uniqueString(resourceGroup().id)

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: '${projectName}-cosmosdb-${uniqueSuffix}'
  location: location
  tags: commonTags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    defaultIdentity: 'FirstWritableLocation'
    enableAutomaticFailover: false
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
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDbAccount
  name: 'order_management_db'
  properties: {
    resource: {
      id: 'order_management_db'
    }
  }
}

// Orders container
resource ordersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'orders'
  properties: {
    resource: {
      id: 'orders'
      partitionKey: {
        paths: [
          '/order_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
      defaultTtl: -1
    }
    options: {
      throughput: 400
    }
  }
}

// Payments container
resource paymentsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'payments'
  properties: {
    resource: {
      id: 'payments'
      partitionKey: {
        paths: [
          '/payment_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
      defaultTtl: -1
    }
    options: {
      throughput: 400
    }
  }
}

// Notifications container
resource notificationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'notifications'
  properties: {
    resource: {
      id: 'notifications'
      partitionKey: {
        paths: [
          '/notification_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
      defaultTtl: 7776000  // 90 days
    }
    options: {
      throughput: 400
    }
  }
}

// Analytics container
resource analyticsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'analytics'
  properties: {
    resource: {
      id: 'analytics'
      partitionKey: {
        paths: [
          '/date'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
      defaultTtl: 31536000  // 1 year
    }
    options: {
      throughput: 400
    }
  }
}

// Service Bus
var uniqueSBSuffix = uniqueString(resourceGroup().id)

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: '${projectName}-sb-${uniqueSBSuffix}'
  location: location
  tags: commonTags
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

// Service Bus Topics
var topicNames = [
  'OrderCreated'
  'OrderCancelled'
  'PaymentProcessed'
  'PaymentFailed'
  'InventoryReserved'
  'InventoryReleased'
]

@batchSize(1)
resource topics 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = [for topicName in topicNames: {
  parent: serviceBusNamespace
  name: topicName
  properties: {
    defaultMessageTimeToLive: 'P14D'
    maxSizeInMegabytes: 1024
    requiresDuplicateDetection: false
  }
}]

output cosmosDbEndpoint string = cosmosDbAccount.properties.documentEndpoint
output serviceBusNamespace string = serviceBusNamespace.name
