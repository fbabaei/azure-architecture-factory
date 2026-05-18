@description('Deployment location')
param location string

@description('Base name for Foundry resources')
param baseName string

@description('Chat model deployment name')
param chatDeploymentName string = 'gpt-4o'

@description('Embeddings model deployment name')
param embeddingsDeploymentName string = 'text-embedding-3-small'

@description('Principal ID of the managed identity')
param identityPrincipalId string

@description('Azure AI Developer role definition resource ID')
param aiDeveloperRoleId string

// AI Services (Cognitive Services kind) — backing resource for Foundry Standard Setup
resource aiServices 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: 'ai-svc-${baseName}'
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: 'ai-svc-${baseName}'
    apiProperties: {}
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// GPT-4o deployment
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: aiServices
  name: chatDeploymentName
  sku: {
    name: 'Standard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// Embeddings deployment
resource embeddingsDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: aiServices
  name: embeddingsDeploymentName
  sku: {
    name: 'Standard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
  dependsOn: [chatDeployment]
}

// AI Developer role for the managed identity
resource aiDeveloperAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, identityPrincipalId, aiDeveloperRoleId)
  scope: aiServices
  properties: {
    roleDefinitionId: aiDeveloperRoleId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Foundry project endpoint convention: https://<custom-subdomain>.services.ai.azure.com/
output projectEndpoint string = 'https://ai-svc-${baseName}.services.ai.azure.com/'
output aiServicesId string = aiServices.id
