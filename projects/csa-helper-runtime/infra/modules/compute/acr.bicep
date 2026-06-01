// Azure Container Registry (Basic) + AcrPull role for the runtime UAMI.
@description('Azure region')
param location string
@description('Registry name (globally unique, lowercase alphanumeric)')
param registryName string
@description('Principal id of the UAMI that should be granted AcrPull')
param pullPrincipalId string
param sku string = 'Basic'
param tags object = {}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: { name: sku }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// AcrPull = 7f951dda-4ed3-4680-a7ca-43fe172d538d
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, pullPrincipalId, 'acrpull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: pullPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = acr.id
output loginServer string = acr.properties.loginServer
output name string = acr.name
