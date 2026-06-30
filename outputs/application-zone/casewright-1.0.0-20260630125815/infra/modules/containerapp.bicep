// Reusable Container App definition used for both casewright-api (external
// ingress) and casewright-worker (no ingress, background Service Bus consumer).
// Pulls images from ACR via the shared user-assigned identity.
param name string
param location string
param tags object = {}

param environmentId string
param identityId string
param registryLoginServer string
param image string

@description('Set true for the API (HTTP ingress); false for the worker.')
param externalIngress bool = false
param targetPort int = 8000

param minReplicas int = 1
param maxReplicas int = 3
param cpu string = '0.5'
param memory string = '1.0Gi'

@description('Environment variables passed to the container.')
param envVars array = []

@description('Optional container entrypoint override (e.g. the worker module).')
param command array = []

@description('azd service name; surfaced as the azd-service-name tag so azd can target this app.')
param serviceName string = ''

var mergedTags = empty(serviceName) ? tags : union(tags, { 'azd-service-name': serviceName })

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: mergedTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: externalIngress ? {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      } : null
      registries: [
        {
          server: registryLoginServer
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: name
          image: image
          command: empty(command) ? null : command
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
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = externalIngress ? app.properties.configuration.ingress.fqdn : ''
