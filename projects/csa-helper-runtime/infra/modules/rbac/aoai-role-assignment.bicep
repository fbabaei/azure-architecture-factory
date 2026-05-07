// Grants `Cognitive Services OpenAI User` to a principal on an EXISTING
// Azure OpenAI account that lives in a different resource group. This module
// is intended to be invoked at resource-group scope by main.bicep with
// `scope: resourceGroup(aoaiResourceGroupName)`.
@description('Name of the EXISTING Azure OpenAI account')
param aoaiAccountName string
@description('Principal id (the user-assigned MI principalId) that needs access')
param principalId string

resource aoai 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' existing = {
  name: aoaiAccountName
}

// Cognitive Services OpenAI User = 5e0bd9bd-7b93-4f28-af87-19fc36ad61bd
resource aoaiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aoai.id, principalId, 'aoai-user')
  scope: aoai
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output aoaiAccountId string = aoai.id
output aoaiEndpoint string = aoai.properties.endpoint
