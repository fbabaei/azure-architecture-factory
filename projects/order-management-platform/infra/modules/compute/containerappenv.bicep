metadata description = 'Container Apps and Registry for OrderManagement Platform'

param location string
param projectName string
param environment string
param commonTags object
@secure()
param appInsightsInstrumentationKey string

var uniqueSuffix = uniqueString(resourceGroup().id)
var acrName = '${projectName}acr${environment}${uniqueSuffix}'

// Azure Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: commonTags
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: true
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'AzureServices'
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      trustPolicy: {
        type: 'Notary'
        status: 'disabled'
      }
      retentionPolicy: {
        days: 30
        status: 'enabled'
      }
    }
  }
}

// Container Apps Environment
var containerAppEnvName = '${projectName}-containerappenv-${environment}'

resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-04-01-preview' = {
  name: '${containerAppEnvName}-${uniqueSuffix}'
  location: location
  tags: commonTags
  properties: {
    daprAIInstrumentationKey: appInsightsInstrumentationKey
  }
}

// Container App: API Gateway
resource apiGatewayApp 'Microsoft.App/containerApps@2023-04-01-preview' = {
  name: '${projectName}-api-gateway-${environment}'
  location: location
  tags: commonTags
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'Auto'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistry.listCredentials().passwords[0].value
        }
      ]
      dapr: {
        enabled: true
        appId: '${projectName}-api-gateway'
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry.properties.loginServer}/${projectName}/api-gateway:latest'
          name: 'api-gateway'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: 'InstrumentationKey=${appInsightsInstrumentationKey}'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// Container App Template for Order Service (and others follow pattern)
resource orderServiceApp 'Microsoft.App/containerApps@2023-04-01-preview' = {
  name: '${projectName}-order-service-${environment}'
  location: location
  tags: commonTags
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8001
        transport: 'Auto'
      }
      dapr: {
        enabled: true
        appId: '${projectName}-order-service'
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry.properties.loginServer}/${projectName}/order-service:latest'
          name: 'order-service'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

output containerRegistryName string = containerRegistry.name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerAppEnvironmentId string = containerAppEnv.id
output containerAppEnvironmentName string = containerAppEnv.name
output apiGatewayAppId string = apiGatewayApp.id
output apiGatewayIngressfqdn string = apiGatewayApp.properties.configuration.ingress.fqdn
output orderServiceAppId string = orderServiceApp.id
