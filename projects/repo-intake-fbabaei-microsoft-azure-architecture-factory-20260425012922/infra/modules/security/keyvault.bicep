// Azure Key Vault Module
// Provides secure storage for secrets, API keys, and connection strings

param location string
param keyVaultName string
param tenantId string
param principalId string
param tags object = {}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    tenantId: tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    accessPolicies: [
      {
        tenantId: tenantId
        objectId: principalId
        permissions: {
          keys: ['get', 'list', 'create', 'delete', 'update']
          secrets: ['get', 'list', 'set', 'delete']
          certificates: ['get', 'list', 'create', 'delete', 'update']
        }
      }
    ]
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

output keyVaultId string = keyVault.id
output vaultUri string = keyVault.properties.vaultUri
