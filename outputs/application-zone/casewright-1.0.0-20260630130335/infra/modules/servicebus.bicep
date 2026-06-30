// Service Bus namespace + queue carrying SharePoint sync requests from the
// scheduler/API (senders) to the worker (receiver). Local auth is disabled —
// all access uses managed identity + Service Bus data-plane RBAC.
param namespaceName string
param location string
param tags object = {}

@allowed([
  'Standard'
  'Premium'
])
param skuName string = 'Standard'

param queueName string = 'sharepoint-sync'

@description('Disable local (SAS) auth. Must stay true per the security audit.')
param disableLocalAuth bool = true

@description('Delivery attempts before a message is moved to the dead-letter queue.')
@minValue(1)
@maxValue(2000)
param maxDeliveryCount int = 5

@description('Peek-lock duration (ISO 8601). Must exceed worst-case processing time.')
param lockDuration string = 'PT5M'

resource namespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuName
  }
  properties: {
    disableLocalAuth: disableLocalAuth
    minimumTlsVersion: '1.2'
  }
}

resource queue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: queueName
  properties: {
    lockDuration: lockDuration
    maxDeliveryCount: maxDeliveryCount
    deadLetteringOnMessageExpiration: true
    defaultMessageTimeToLive: 'P7D'
    maxSizeInMegabytes: 1024
    enablePartitioning: false
  }
}

output id string = namespace.id
output name string = namespace.name
output fqdn string = '${namespace.name}.servicebus.windows.net'
output queueName string = queue.name
output maxDeliveryCount int = maxDeliveryCount
