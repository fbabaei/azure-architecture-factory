@description('Deployment location')
param location string

@description('Service Bus namespace name')
param sbNamespaceName string

@description('Service Bus SKU')
param sbSku string = 'Standard'

@description('Principal ID of the managed identity')
param identityPrincipalId string

@description('Service Bus Data Owner role definition resource ID')
param serviceBusDataOwnerRoleId string

resource sbNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: sbNamespaceName
  location: location
  sku: {
    name: sbSku
  }
  properties: {}
}

resource tasksQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'daop-tasks'
  properties: {
    maxDeliveryCount: 5
    defaultMessageTimeToLive: 'PT4H'
    lockDuration: 'PT5M'
  }
}

resource resultsQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'daop-results'
  properties: {
    maxDeliveryCount: 5
    defaultMessageTimeToLive: 'PT4H'
    lockDuration: 'PT5M'
  }
}

resource hitlQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'daop-hitl'
  properties: {
    maxDeliveryCount: 3
    defaultMessageTimeToLive: 'P1D'
    lockDuration: 'PT1M'
  }
}

resource sbRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sbNamespace.id, identityPrincipalId, serviceBusDataOwnerRoleId)
  scope: sbNamespace
  properties: {
    roleDefinitionId: serviceBusDataOwnerRoleId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output namespace string = sbNamespace.name
output fqns string = '${sbNamespace.name}.servicebus.windows.net'
