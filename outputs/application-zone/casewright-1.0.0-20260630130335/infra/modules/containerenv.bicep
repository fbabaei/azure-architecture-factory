// Container Apps managed environment hosting casewright-api and
// casewright-worker, wired to the Log Analytics workspace for logs.
param name string
param location string
param tags object = {}

param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
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

output id string = environment.id
output name string = environment.name
output defaultDomain string = environment.properties.defaultDomain
