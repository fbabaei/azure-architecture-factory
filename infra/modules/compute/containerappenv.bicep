// Container Apps Environment and Agent Service Module
// Hosts the agentic application with automatic scaling and integrated networking

param location string
param containerEnvName string
param containerAppName string
param containerImageUri string
param containerPort int
@secure()
param appInsightsInstrumentationKey string
param managedIdentityId string
@secure()
param keyVaultUrl string
param workspaceId string
param environment string
param projectName string
param tags object = {}

// Log Analytics workspace for Container Apps
resource containerEnvLogAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: split(workspaceId, '/')[8]
}

// Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-02-preview' = {
  name: containerEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: containerEnvLogAnalytics.properties.customerId
        sharedKey: listKeys(workspaceId, '2022-10-01').primarySharedKey
      }
    }
  }
}

// Container App (Agent Service)
resource containerApp 'Microsoft.App/containerApps@2023-05-02-preview' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'multiple'
      ingress: {
        external: true
        targetPort: containerPort
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: []
      secrets: [
        {
          name: 'appinsights-key'
          value: appInsightsInstrumentationKey
          identity: managedIdentityId
        }
        {
          name: 'keyvault-url'
          value: keyVaultUrl
          identity: managedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          image: containerImageUri
          name: 'agent'
          resources: {
            cpu: 1
            memory: '1Gi'
          }
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-key'
            }
            {
              name: 'KEY_VAULT_URL'
              secretRef: 'keyvault-url'
            }
            {
              name: 'ENVIRONMENT'
              value: environment
            }
            {
              name: 'PROJECT_NAME'
              value: projectName
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: environment == 'prod' ? 10 : 3
        rules: [
          {
            name: 'http-requests'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

output containerAppId string = containerApp.id
output containerAppName string = containerApp.name
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerAppEnvId string = containerAppEnv.id
