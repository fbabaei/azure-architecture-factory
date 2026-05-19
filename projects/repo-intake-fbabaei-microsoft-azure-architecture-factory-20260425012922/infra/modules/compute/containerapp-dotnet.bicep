// Container App Module — .NET variant
// Deploys an ASP.NET Core (net8.0) service onto an existing Container Apps Environment
// with .NET-idiomatic defaults: port 8080, ASPNETCORE_URLS, managed identity, and
// /health + /health/ready probes.
//
// Use this module when BRD.implementation.language == "dotnet". For Python services,
// use compute/containerapp.bicep.

param location string
param containerAppName string
param containerEnvId string
param containerImageUri string
param managedIdentityId string
param environment string
param tags object = {}

@description('Container port. Default 8080 aligns with the lang-dotnet Dockerfile template.')
param containerPort int = 8080

@description('CPU cores allocated to the container')
param cpu string = '0.5'

@description('Memory allocated to the container')
param memory string = '1Gi'

@description('Minimum replica count')
param minReplicas int = 1

@description('Maximum replica count')
param maxReplicas int = 5

@description('Additional environment variables as name/value pairs. ASPNETCORE_* defaults are added automatically.')
param envVars array = []

@description('Secret references as name/value pairs')
param secrets array = []

@description('Container registry configuration entries')
param registries array = []

@description('Whether ingress is external (internet-facing)')
param externalIngress bool = true

@description('Application Insights connection string. If provided, wired into APPLICATIONINSIGHTS_CONNECTION_STRING.')
param appInsightsConnectionString string = ''

@description('ASP.NET Core environment name. Production for non-dev, Development otherwise.')
param aspNetCoreEnvironment string = environment == 'dev' ? 'Development' : 'Production'

// .NET-idiomatic env vars appended to anything the caller provides
var dotnetEnvVars = concat(
  [
    { name: 'ASPNETCORE_URLS',          value: 'http://+:${containerPort}' }
    { name: 'ASPNETCORE_ENVIRONMENT',   value: aspNetCoreEnvironment }
    { name: 'DOTNET_RUNNING_IN_CONTAINER', value: 'true' }
    { name: 'DOTNET_SYSTEM_GLOBALIZATION_INVARIANT', value: 'false' }
  ],
  empty(appInsightsConnectionString) ? [] : [
    { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
  ],
  envVars
)

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
    managedEnvironmentId: containerEnvId
    configuration: {
      activeRevisionsMode: 'single'
      registries: registries
      secrets: secrets
      ingress: {
        external: externalIngress
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
    }
    template: {
      containers: [
        {
          name: containerAppName
          image: containerImageUri
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: dotnetEnvVars
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: containerPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health/ready'
                port: containerPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 15
              failureThreshold: 3
            }
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: containerPort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: '50'
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
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
