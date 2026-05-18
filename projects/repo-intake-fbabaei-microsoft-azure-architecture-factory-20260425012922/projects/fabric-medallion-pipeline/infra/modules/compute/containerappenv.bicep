// Container Apps Environment module

param name string
param location string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param tags object = {}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
  }
}

output environmentId string = containerAppEnv.id
output environmentName string = containerAppEnv.name
output defaultDomain string = containerAppEnv.properties.defaultDomain
