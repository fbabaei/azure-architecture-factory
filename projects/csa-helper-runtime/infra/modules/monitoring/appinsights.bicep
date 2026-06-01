// Application Insights (workspace-based)
@description('Azure region')
param location string
@description('App Insights resource name')
param appInsightsName string
@description('Backing Log Analytics workspace resource id')
param workspaceId string
param tags object = {}

resource ai 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    IngestionMode: 'LogAnalytics'
    WorkspaceResourceId: workspaceId
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output id string = ai.id
output instrumentationKey string = ai.properties.InstrumentationKey
output connectionString string = ai.properties.ConnectionString
