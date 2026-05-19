targetScope = 'resourceGroup'

@description('Deployment location')
param location string = resourceGroup().location

@description('Environment name')
param environment string = 'dev'

@description('Logical workload name used in generated resource names')
param workloadName string = 'starter-workload'

@description('Whether the starter should include monitoring and observability resources')
param enableObservability bool = true

@description('Optional operations email for alert notifications. Leave empty to skip email actions.')
param operationsEmail string = ''


var resourceBaseName = toLower(replace('${workloadName}-${environment}', '_', '-'))

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = if (enableObservability) {
  name: '${resourceBaseName}-law'
  location: location
  properties: {
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
  sku: {
    name: 'PerGB2018'
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = if (enableObservability) {
  name: '${resourceBaseName}-appi'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    IngestionMode: 'LogAnalytics'
  }
}

resource operationsActionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (enableObservability && !empty(operationsEmail)) {
  name: '${resourceBaseName}-opsag'
  location: 'global'
  properties: {
    enabled: true
    groupShortName: 'opsalert'
    emailReceivers: [
      {
        name: 'operations-team'
        emailAddress: operationsEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

output deploymentHint string = 'Replace this starter Bicep file with workload-specific Azure resources.'
output locationUsed string = location
output environmentName string = environment
output observabilityEnabled bool = enableObservability
output logAnalyticsWorkspaceName string = enableObservability ? logAnalyticsWorkspace.name : 'not-enabled'
output appInsightsName string = enableObservability ? applicationInsights.name : 'not-enabled'
output appInsightsConnectionString string = enableObservability ? applicationInsights.properties.ConnectionString : ''
output actionGroupName string = (enableObservability && !empty(operationsEmail)) ? operationsActionGroup.name : 'not-configured'
