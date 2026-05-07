// Container Apps Environment (workspace-attached).
@description('Azure region')
param location string
@description('Environment name')
param envName string
@description('Backing Log Analytics workspace resource id')
param workspaceId string
param tags object = {}

resource law 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: last(split(workspaceId, '/'))
}

resource cae 'Microsoft.App/managedEnvironments@2023-05-02-preview' = {
  name: envName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
  }
}

output id string = cae.id
output name string = cae.name
