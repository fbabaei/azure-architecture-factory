// Key Vault (RBAC) + 'aoai-endpoint' secret + Key Vault Secrets User role
// for the runtime UAMI.
@description('Azure region')
param location string
@description('Key Vault name (globally unique)')
param keyVaultName string
@description('Tenant id')
param tenantId string = subscription().tenantId
@description('Principal id of the UAMI that needs read access to secrets')
param secretsUserPrincipalId string
@description('Plaintext AOAI endpoint URL — stored as a secret on first deployment')
@secure()
param aoaiEndpoint string
param tags object = {}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enabledForDeployment: false
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource aoaiEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: 'aoai-endpoint'
  parent: kv
  properties: {
    value: aoaiEndpoint
    contentType: 'text/plain'
  }
}

// Key Vault Secrets User = 4633458b-17de-408a-b874-0445c86b69e6
resource secretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, secretsUserPrincipalId, 'kv-secrets-user')
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: secretsUserPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = kv.id
output name string = kv.name
output uri string = kv.properties.vaultUri
output aoaiEndpointSecretUri string = aoaiEndpointSecret.properties.secretUri
