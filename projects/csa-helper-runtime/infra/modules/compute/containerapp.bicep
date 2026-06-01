// Container App for the csa-helper runtime.
//
// - Public ingress on 8080.
// - User-assigned managed identity (single).
// - Pulls image from ACR using the same UAMI (AcrPull granted in acr.bicep).
// - AZURE_OPENAI_ENDPOINT is sourced from a Key Vault secret reference; the
//   secret store is wired with `keyVaultUrl` + UAMI per Container Apps spec.
@description('Azure region')
param location string
@description('Container App name')
param containerAppName string
@description('Container Apps Environment resource id')
param containerEnvId string
@description('Full image reference (e.g. <acr>.azurecr.io/csa-helper-runtime:tag)')
param containerImage string
@description('User-assigned managed identity resource id')
param managedIdentityId string
@description('ACR login server (e.g. <acr>.azurecr.io)')
param acrLoginServer string
@description('App Insights connection string')
@secure()
param appInsightsConnectionString string
@description('Key Vault secret URI for the AOAI endpoint (e.g. https://<kv>.vault.azure.net/secrets/aoai-endpoint)')
param aoaiEndpointSecretUri string
@description('AOAI deployment name (plain env var)')
param aoaiDeployment string = 'gpt-4o'
@description('AOAI api-version (plain env var)')
param aoaiApiVersion string = '2024-10-21'
@description('Min replicas')
param minReplicas int = 0
@description('Max replicas')
param maxReplicas int = 3
param tags object = {}

resource capp 'Microsoft.App/containerApps@2023-05-02-preview' = {
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
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
        traffic: [
          { latestRevision: true, weight: 100 }
        ]
      }
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
      secrets: [
        {
          name: 'appinsights-cs'
          value: appInsightsConnectionString
        }
        {
          name: 'aoai-endpoint'
          keyVaultUrl: aoaiEndpointSecretUri
          identity: managedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'runtime'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', secretRef: 'aoai-endpoint' }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: aoaiDeployment }
            { name: 'AZURE_OPENAI_API_VERSION', value: aoaiApiVersion }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-cs' }
            { name: 'AZURE_CLIENT_ID', value: reference(managedIdentityId, '2023-01-31').clientId }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health/ready', port: 8080 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-concurrency'
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

output id string = capp.id
output fqdn string = capp.properties.configuration.ingress.fqdn
output url string = 'https://${capp.properties.configuration.ingress.fqdn}'
