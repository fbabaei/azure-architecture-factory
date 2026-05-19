metadata description = 'Key Vault and Managed Identities for OrderManagement Platform'

param location string
param projectName string
param environment string
param commonTags object

var uniqueSuffix = uniqueString(resourceGroup().id)

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${projectName}-kv-${uniqueSuffix}'
  location: location
  tags: commonTags
  properties: {
    enabledForDeployment: true
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    accessPolicies: []
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Managed Identity for API Gateway
resource apiGatewayMI 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-api-gateway-mi-${environment}'
  location: location
  tags: commonTags
}

// Managed Identity for Order Service
resource orderServiceMI 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-order-service-mi-${environment}'
  location: location
  tags: commonTags
}

// Managed Identity for Inventory Service
resource inventoryServiceMI 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-inventory-service-mi-${environment}'
  location: location
  tags: commonTags
}

// Managed Identity for Payment Service
resource paymentServiceMI 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-payment-service-mi-${environment}'
  location: location
  tags: commonTags
}

// Managed Identity for Notification Service
resource notificationServiceMI 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-notification-service-mi-${environment}'
  location: location
  tags: commonTags
}

// Managed Identity for Analytics Service
resource analyticsServiceMI 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-analytics-service-mi-${environment}'
  location: location
  tags: commonTags
}

output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
output apiGatewayMIId string = apiGatewayMI.id
output orderServiceMIId string = orderServiceMI.id
output inventoryServiceMIId string = inventoryServiceMI.id
output paymentServiceMIId string = paymentServiceMI.id
output notificationServiceMIId string = notificationServiceMI.id
output analyticsServiceMIId string = analyticsServiceMI.id
