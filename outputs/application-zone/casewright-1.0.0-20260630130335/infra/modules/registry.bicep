// Azure Container Registry hosting the casewright-api and casewright-worker
// images. Admin user disabled — the Container Apps pull via the shared
// user-assigned identity (AcrPull granted in modules/rbac.bicep).
param name string
param location string
param tags object = {}

@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param skuName string = 'Standard'

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    anonymousPullEnabled: false
  }
}

output id string = registry.id
output name string = registry.name
output loginServer string = registry.properties.loginServer
