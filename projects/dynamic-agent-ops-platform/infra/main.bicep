targetScope = 'resourceGroup'

@description('Deployment location')
param location string = resourceGroup().location

@description('Environment suffix (dev, staging, prod)')
param environment string = 'dev'

@description('Logical workload name used to derive resource names')
param workloadName string = 'daop'

@description('Azure AI Foundry model deployment name for all agents')
param foundryModelDeployment string = 'gpt-4o'

@description('Azure AI Foundry embeddings deployment name')
param foundryEmbeddingsDeployment string = 'text-embedding-3-small'

@description('Container image tag for all agent services. Leave empty to use latest build.')
param imageTag string = 'latest'

@description('Orchestrator minimum replicas (always-on)')
param orchestratorMinReplicas int = 1

@description('Sub-agent minimum replicas (scale-to-zero by default)')
param subAgentMinReplicas int = 0

@description('Cosmos DB throughput RU/s for dev')
param cosmosThroughput int = 400

@description('Service Bus SKU')
param serviceBusSku string = 'Standard'

@secure()
@description('AAF API base URL for the architect agent AAF tool (optional)')
param aafApiBaseUrl string = ''

// ---------------------------------------------------------------------------
// Derived names
// ---------------------------------------------------------------------------
var baseName = toLower(replace('${workloadName}-${environment}', '_', '-'))
var unique = uniqueString(resourceGroup().id, baseName)
var acrName = take('acr${unique}', 50)
var kvName = take('kv-${baseName}-${take(unique, 6)}', 24)
var cosmosAccountName = take('cosmos-${baseName}-${take(unique, 8)}', 44)
var sbNamespaceName = take('sb-${baseName}-${take(unique, 8)}', 50)
var logWorkspaceName = 'log-${baseName}'
var appInsightsName = 'ai-${baseName}'
var identityName = 'id-${baseName}'
var caEnvName = 'cae-${baseName}'

// ---------------------------------------------------------------------------
// Role definition IDs
// ---------------------------------------------------------------------------
var roleIds = {
  keyVaultSecretsUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  cosmosDbDataContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00000000-0000-0000-0000-000000000002')
  serviceBusDataOwner: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '090c5cfd-751d-490a-894a-3ce6f1109419')
  acrPull: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  azureAiDeveloper: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
}

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------
module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    identityName: identityName
  }
}

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    acrName: acrName
    identityPrincipalId: identity.outputs.principalId
    acrPullRoleId: roleIds.acrPull
  }
}

module observability 'modules/observability.bicep' = {
  name: 'observability'
  params: {
    location: location
    logWorkspaceName: logWorkspaceName
    appInsightsName: appInsightsName
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVault'
  params: {
    location: location
    kvName: kvName
    identityPrincipalId: identity.outputs.principalId
    kvSecretsUserRoleId: roleIds.keyVaultSecretsUser
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    location: location
    cosmosAccountName: cosmosAccountName
    databaseName: 'daop'
    throughput: cosmosThroughput
    identityPrincipalId: identity.outputs.principalId
  }
}

module serviceBus 'modules/servicebus.bicep' = {
  name: 'serviceBus'
  params: {
    location: location
    sbNamespaceName: sbNamespaceName
    sbSku: serviceBusSku
    identityPrincipalId: identity.outputs.principalId
    serviceBusDataOwnerRoleId: roleIds.serviceBusDataOwner
  }
}

module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  params: {
    location: location
    baseName: baseName
    chatDeploymentName: foundryModelDeployment
    embeddingsDeploymentName: foundryEmbeddingsDeployment
    identityPrincipalId: identity.outputs.principalId
    aiDeveloperRoleId: roleIds.azureAiDeveloper
  }
}

module containerAppEnv 'modules/containerapp-env.bicep' = {
  name: 'containerAppEnv'
  params: {
    location: location
    caEnvName: caEnvName
    logWorkspaceId: observability.outputs.logWorkspaceId
    logWorkspaceKey: observability.outputs.logWorkspaceKey
  }
}

// ---------------------------------------------------------------------------
// Common env vars shared by all container apps
// ---------------------------------------------------------------------------
var commonEnv = [
  { name: 'COSMOS_ENDPOINT', value: cosmos.outputs.endpoint }
  { name: 'COSMOS_DATABASE', value: 'daop' }
  { name: 'SERVICEBUS_NAMESPACE', value: serviceBus.outputs.namespace }
  { name: 'SERVICEBUS_TASKS_QUEUE', value: 'daop-tasks' }
  { name: 'SERVICEBUS_RESULTS_QUEUE', value: 'daop-results' }
  { name: 'SERVICEBUS_HITL_QUEUE', value: 'daop-hitl' }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: observability.outputs.appInsightsConnectionString }
  { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundry.outputs.projectEndpoint }
  { name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME', value: foundryModelDeployment }
  { name: 'AGENT_FRAMEWORK_ENABLED', value: '1' }
]

module orchestratorApp 'modules/containerapp.bicep' = {
  name: 'orchestratorApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-orchestrator'
    image: '${acr.outputs.loginServer}/daop-orchestrator:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: orchestratorMinReplicas
    maxReplicas: 10
    port: 8080
    envVars: concat(commonEnv, [
      { name: 'AGENT_FACTORY_URL', value: 'http://daop-agent-factory' }
      { name: 'AGENT_REGISTRY_URL', value: 'http://daop-agent-registry' }
      { name: 'HITL_ENABLED', value: '1' }
    ])
  }
}

module agentFactoryApp 'modules/containerapp.bicep' = {
  name: 'agentFactoryApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-agent-factory'
    image: '${acr.outputs.loginServer}/daop-agent-factory:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: subAgentMinReplicas
    maxReplicas: 5
    port: 8081
    envVars: concat(commonEnv, [
      { name: 'AGENT_REGISTRY_URL', value: 'http://daop-agent-registry' }
    ])
  }
}

module agentRegistryApp 'modules/containerapp.bicep' = {
  name: 'agentRegistryApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-agent-registry'
    image: '${acr.outputs.loginServer}/daop-agent-registry:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: 1
    maxReplicas: 3
    port: 8082
    envVars: commonEnv
  }
}

module architectApp 'modules/containerapp.bicep' = {
  name: 'architectApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-agent-architect'
    image: '${acr.outputs.loginServer}/daop-agent-architect:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: subAgentMinReplicas
    maxReplicas: 5
    port: 8090
    envVars: concat(commonEnv, [
      { name: 'AAF_API_BASE_URL', value: aafApiBaseUrl }
    ])
  }
}

module developerApp 'modules/containerapp.bicep' = {
  name: 'developerApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-agent-developer'
    image: '${acr.outputs.loginServer}/daop-agent-developer:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: subAgentMinReplicas
    maxReplicas: 5
    port: 8091
    envVars: commonEnv
  }
}

module opsApp 'modules/containerapp.bicep' = {
  name: 'opsApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-agent-ops'
    image: '${acr.outputs.loginServer}/daop-agent-ops:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: subAgentMinReplicas
    maxReplicas: 5
    port: 8092
    envVars: commonEnv
  }
}

module analystApp 'modules/containerapp.bicep' = {
  name: 'analystApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-agent-analyst'
    image: '${acr.outputs.loginServer}/daop-agent-analyst:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: subAgentMinReplicas
    maxReplicas: 5
    port: 8093
    envVars: commonEnv
  }
}

module securityApp 'modules/containerapp.bicep' = {
  name: 'securityApp'
  params: {
    location: location
    caEnvId: containerAppEnv.outputs.envId
    appName: 'daop-agent-security'
    image: '${acr.outputs.loginServer}/daop-agent-security:${imageTag}'
    identityId: identity.outputs.identityId
    minReplicas: subAgentMinReplicas
    maxReplicas: 5
    port: 8094
    envVars: commonEnv
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output orchestratorFqdn string = orchestratorApp.outputs.fqdn
output acrLoginServer string = acr.outputs.loginServer
output cosmosEndpoint string = cosmos.outputs.endpoint
output serviceBusNamespace string = serviceBus.outputs.namespace
output foundryProjectEndpoint string = foundry.outputs.projectEndpoint
output appInsightsConnectionString string = observability.outputs.appInsightsConnectionString
