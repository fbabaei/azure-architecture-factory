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

@description('Address prefix for the virtual network')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Address prefix for the application subnet')
param appSubnetPrefix string = '10.0.0.0/24'

@description('Address prefix for the private endpoint subnet')
param peSubnetPrefix string = '10.0.1.0/24'


var resourceBaseName = toLower(replace('${workloadName}-${environment}', '_', '-'))

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-04-01' = {
  name: '${resourceBaseName}-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'deny-inbound-default'
        properties: {
          priority: 4000
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' = {
  name: '${resourceBaseName}-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: [ vnetAddressPrefix ] }
    subnets: [
      {
        name: 'app-subnet'
        properties: {
          addressPrefix: appSubnetPrefix
          networkSecurityGroup: { id: nsg.id }
          delegations: [
            {
              name: 'app-env-delegation'
              properties: { serviceName: 'Microsoft.App/environments' }
            }
          ]
        }
      }
      {
        name: 'pe-subnet'
        properties: {
          addressPrefix: peSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
  dependsOn: [ nsg ]
}

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
output vnetName string = vnet.name
output appSubnetId string = vnet.properties.subnets[0].id
output peSubnetId string = vnet.properties.subnets[1].id
