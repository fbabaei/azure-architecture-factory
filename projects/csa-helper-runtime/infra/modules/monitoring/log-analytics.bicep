// Log Analytics Workspace
@description('Azure region')
param location string
@description('Workspace name')
param workspaceName string
@description('Retention in days')
param retentionInDays int = 30
param tags object = {}

resource law 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: retentionInDays
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output id string = law.id
output customerId string = law.properties.customerId
output name string = law.name
