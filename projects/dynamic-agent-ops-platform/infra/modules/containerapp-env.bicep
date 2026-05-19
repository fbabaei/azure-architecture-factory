@description('Deployment location')
param location string

@description('Container App Environment name')
param caEnvName string

@description('Log Analytics workspace resource ID')
param logWorkspaceId string

@description('Log Analytics workspace primary shared key')
@secure()
param logWorkspaceKey string

resource caEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: caEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logWorkspaceId, '2022-10-01').customerId
        sharedKey: logWorkspaceKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

output envId string = caEnv.id
output envName string = caEnv.name
