// Azure AI Foundry account (kind=AIServices, project management enabled) plus a
// Foundry project. Hosts the Casewright `case-knowledge-agent` (Foundry Agent
// Service) which retrieves from the Search knowledge base over an MCP tool.
// Entra-only: local auth disabled. The project's system-assigned identity is
// granted Search + model access in modules/rbac.bicep.

@description('Name of the AI Foundry (AIServices) account.')
@minLength(2)
@maxLength(64)
param name string

@description('Name of the Foundry project under the account.')
@minLength(2)
@maxLength(64)
param projectName string

@description('Azure region.')
param location string = resourceGroup().location

@description('Tags to apply.')
param tags object = {}

@description('Custom subdomain. Required for Entra ID auth + the Foundry endpoint host.')
param customSubDomainName string = toLower(name)

@description('Public network access setting.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@description('Disable local (key-based) auth. Must stay true per the security audit.')
param disableLocalAuth bool = true

@description('Chat model deployment used by the hosted agent: name + model + version + capacity.')
param chatDeployment object = {
  name: 'gpt-4o'
  model: 'gpt-4o'
  version: '2024-11-20'
  capacity: 10
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: customSubDomainName
    disableLocalAuth: disableLocalAuth
    publicNetworkAccess: publicNetworkAccess
    allowProjectManagement: true
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
  }
}

// Chat model deployment the hosted agent references by name.
resource chat 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
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

// Foundry project — the agent host. Deployment ordering after the model
// deployment keeps a single in-flight account operation at a time.
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: projectName
    description: 'Casewright hosted knowledge agent project.'
  }
  dependsOn: [
    chat
  ]
}

output accountId string = foundry.id
output accountName string = foundry.name
output accountEndpoint string = foundry.properties.endpoint
output projectId string = project.id
output projectName string = project.name
output projectPrincipalId string = project.identity.principalId
output chatDeploymentName string = chat.name
// Foundry project endpoint expected by the Agents SDK / deploy_agent.py.
output projectEndpoint string = 'https://${customSubDomainName}.services.ai.azure.com/api/projects/${projectName}'
