// Container App Module
// Deploys a single container app into an existing Container Apps Environment

param location string
param containerAppName string
param containerEnvId string
param containerImageUri string
param containerPort int
param managedIdentityId string
param environment string // used by callers for scale rules
param tags object = {}

@description('CPU cores allocated to the container')
param cpu string = '0.5'

@description('Memory allocated to the container')
param memory string = '1Gi'

@description('Minimum replica count')
param minReplicas int = 1

@description('Maximum replica count')
param maxReplicas int = 3

@description('Environment variables as name/value pairs')
param envVars array = []

@description('Secret references as name/value pairs')
param secrets array = []

@description('Container registry configuration entries')
param registries array = []

@description('Whether ingress is external (internet-facing)')
param externalIngress bool = true

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
      secrets: secrets
    }
    template: {
      containers: [
        {
          image: containerImageUri
          name: containerAppName
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: envVars
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
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

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output url string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output id string = containerApp.id
