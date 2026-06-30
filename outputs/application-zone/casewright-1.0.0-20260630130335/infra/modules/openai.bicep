// Azure OpenAI (Cognitive Services) account with the chat and embedding model
// deployments Casewright depends on. Entra-only: local auth disabled. Callers
// (api + Search service identity) authenticate via Cognitive Services OpenAI
// User RBAC (see modules/rbac.bicep).
param name string
param location string
param tags object = {}

@description('Custom subdomain for token-based (Entra) access.')
param customSubDomainName string = toLower(name)

@description('Disable local (key) auth. Must stay true per the security audit.')
param disableLocalAuth bool = true

@description('Chat model deployment: name + model + capacity.')
param chatDeployment object = {
  name: 'gpt-4o'
  model: 'gpt-4o'
  version: '2024-11-20'
  capacity: 30
}

@description('Embedding model deployment: name + model + capacity.')
param embeddingDeployment object = {
  name: 'text-embedding-3-large'
  model: 'text-embedding-3-large'
  version: '1'
  capacity: 50
}

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: customSubDomainName
    disableLocalAuth: disableLocalAuth
    publicNetworkAccess: 'Enabled'
  }
}

resource chat 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: chatDeployment.name
  sku: {
    name: 'GlobalStandard'
    capacity: chatDeployment.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatDeployment.model
      version: chatDeployment.version
    }
  }
}

resource embedding 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: embeddingDeployment.name
  // Sequential dependency: a CognitiveServices account allows only one
  // in-flight deployment operation at a time.
  dependsOn: [
    chat
  ]
  sku: {
    name: 'Standard'
    capacity: embeddingDeployment.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingDeployment.model
      version: embeddingDeployment.version
    }
  }
}

output id string = openai.id
output name string = openai.name
output endpoint string = openai.properties.endpoint
output chatDeploymentName string = chat.name
output embeddingDeploymentName string = embedding.name
