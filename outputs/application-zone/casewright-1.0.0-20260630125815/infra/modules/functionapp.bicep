// Scheduler Function App (Flex Consumption, Python). Fans SharePoint sync
// requests onto Service Bus on a timer / on demand. Key-free: AzureWebJobsStorage
// and deployment storage authenticate with the shared user-assigned identity.
param name string
param location string
param tags object = {}

param planName string
param storageAccountName string
param deploymentContainerName string = 'scheduler-deploy'

param identityId string
param identityClientId string
param appInsightsConnectionString string

@description('Additional app settings (queue, graph, sync schedule, etc.).')
param appSettings array = []

@description('azd service name; surfaced as the azd-service-name tag so azd can target this app.')
param serviceName string = ''

var functionTags = empty(serviceName) ? tags : union(tags, { 'azd-service-name': serviceName })

param pythonVersion string = '3.11'

// Dedicated storage for the Functions host (runtime + deployment package).
resource functionStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: functionStorage
  name: 'default'
}

resource deployContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: deploymentContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  tags: tags
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  kind: 'functionapp'
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  tags: functionTags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${functionStorage.properties.primaryEndpoints.blob}${deploymentContainerName}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: identityId
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 40
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: pythonVersion
      }
    }
    siteConfig: {
      appSettings: concat(
        [
          {
            name: 'AzureWebJobsStorage__accountName'
            value: functionStorage.name
          }
          {
            name: 'AzureWebJobsStorage__credential'
            value: 'managedidentity'
          }
          {
            name: 'AzureWebJobsStorage__clientId'
            value: identityClientId
          }
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: appInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: identityClientId
          }
        ],
        appSettings
      )
    }
  }
}

output id string = functionApp.id
output name string = functionApp.name
output defaultHostName string = functionApp.properties.defaultHostName
output storageAccountName string = functionStorage.name
