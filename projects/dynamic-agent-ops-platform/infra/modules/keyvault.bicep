@description('Deployment location')
param location string

@description('Key Vault name (max 24 chars)')
param kvName string

@description('Principal ID of the managed identity')
param identityPrincipalId string

@description('Key Vault Secrets User role definition resource ID')
param kvSecretsUserRoleId string

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource kvSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identityPrincipalId, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: kvSecretsUserRoleId
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output kvId string = keyVault.id
output kvUri string = keyVault.properties.vaultUri
