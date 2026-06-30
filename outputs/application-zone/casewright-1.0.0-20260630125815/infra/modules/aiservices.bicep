// Azure AI multi-service Cognitive Services account (kind=CognitiveServices).
// Provides Document Intelligence, Vision, Language, and Content Safety under a
// single endpoint. Casewright's Azure AI Search multimodal skillset attaches
// this account (via AIServicesAccountIdentity) so the DocumentIntelligence
// Layout and ChatCompletion skills can run. Entra-only: local auth disabled.

@description('Name of the Cognitive Services multi-service account.')
@minLength(2)
@maxLength(64)
param name string

@description('Azure region.')
param location string = resourceGroup().location

@description('Tags to apply.')
param tags object = {}

@description('SKU name. S0 enables all services under the multi-service account.')
param skuName string = 'S0'

@description('Custom subdomain. Required for Entra ID auth. Must be globally unique.')
param customSubDomainName string = toLower(name)

@description('Public network access setting.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@description('Disable local (key-based) auth. Must stay true per the security audit.')
param disableLocalAuth bool = true

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'CognitiveServices'
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: customSubDomainName
    disableLocalAuth: disableLocalAuth
    publicNetworkAccess: publicNetworkAccess
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
  }
}

output id string = aiServices.id
output name string = aiServices.name
output endpoint string = aiServices.properties.endpoint
output principalId string = aiServices.identity.principalId
