targetScope = 'resourceGroup'

@description('Deployment location')
param location string = resourceGroup().location

@description('Environment suffix (dev, test, prod)')
param environment string = 'dev'

@description('Logical workload name used to derive resource names')
param workloadName string = 'mdr-support'

@description('Wire Application Insights + Log Analytics into the workload')
param enableObservability bool = true

@description('Operations email for action group notifications (optional)')
param operationsEmail string = ''

@description('Azure OpenAI SKU (e.g. S0)')
param openAiSku string = 'S0'

@description('Azure AI Search SKU (basic or standard)')
param aiSearchSku string = 'basic'

@description('Azure OpenAI chat deployment name (e.g. gpt-5.2)')
param openAiChatDeployment string = 'gpt-5.2'

@description('Azure OpenAI chat model name')
param openAiChatModel string = 'gpt-5.2'

@description('Azure OpenAI embeddings deployment name')
param openAiEmbeddingsDeployment string = 'text-embedding-3-small'

@description('Azure OpenAI embeddings model name')
param openAiEmbeddingsModel string = 'text-embedding-3-small'

@description('Optional audience for APIM JWT validation. Leave empty to skip validate-jwt.')
param apiAudience string = ''

@description('Container image for the MDR agent API. When empty, the ACR-hosted image tag \'mdr-agent:latest\' is used.')
param containerImage string = ''

@description('Provision an Azure Container Registry in this resource group for the MDR agent image.')
param provisionAcr bool = true


var baseName = toLower(replace('${workloadName}-${environment}', '_', '-'))
var acrName = take('acr${uniqueString(resourceGroup().id, baseName)}', 50)
var storageName = take('stg${uniqueString(resourceGroup().id, baseName)}', 24)
var openIdConfigUrl = '${az.environment().authentication.loginEndpoint}${subscription().tenantId}/v2.0/.well-known/openid-configuration'
var apimPolicyXml = empty(apiAudience)
  ? '<policies><inbound><base /><rate-limit-by-key calls="60" renewal-period="60" counter-key="@(context.Subscription?.Key ?? context.Request.IpAddress)" /><set-backend-service backend-id="mdr-agent-backend" /></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
  : '<policies><inbound><base /><validate-jwt header-name="Authorization" require-scheme="Bearer" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized"><openid-config url="${openIdConfigUrl}" /><audiences><audience>${apiAudience}</audience></audiences></validate-jwt><rate-limit-by-key calls="60" renewal-period="60" counter-key="@(context.Subscription?.Key ?? context.Request.IpAddress)" /><set-backend-service backend-id="mdr-agent-backend" /></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
var roleDefinitionIds = {
  openAiUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  cognitiveServicesUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  blobContributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  keyVaultSecretsUser: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  searchIndexReader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  acrPull: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
}

// Cosmos data-plane role IDs are scoped to the account, not the subscription.
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'
var tags = {
  workload: workloadName
  environment: environment
  purpose: 'mdr-arrangement-extraction'
}


// Identity + secrets
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${baseName}-mi'
  location: location
  tags: tags
}

// Container Registry (optional — when provisionAcr is true, a new ACR is created
// in this resource group and AcrPull is granted to the managed identity. When
// false, the caller must pass containerImage pointing to an existing registry
// and optionally existingAcrResourceId to grant AcrPull on it.)
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = if (provisionAcr) {
  name: acrName
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

var effectiveContainerImage = !empty(containerImage)
  ? containerImage
  : (provisionAcr ? '${acr!.properties.loginServer}/mdr-agent:latest' : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest')

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take('${baseName}-kv', 24)
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    publicNetworkAccess: 'Enabled'
  }
}

// Observability
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = if (enableObservability) {
  name: '${baseName}-law'
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (enableObservability) {
  name: '${baseName}-appi'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (enableObservability && !empty(operationsEmail)) {
  name: '${baseName}-ag'
  location: 'global'
  properties: {
    enabled: true
    groupShortName: 'mdrops'
    emailReceivers: [
      {
        name: 'mdr-operations'
        emailAddress: operationsEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

// Storage: uploaded MDR source documents
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'mdr-documents'
  properties: { publicAccess: 'None' }
}

resource knowledgeBaseContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'knowledge-base-source'
  properties: { publicAccess: 'None' }
}

// Cosmos DB: arrangement drafts + chat sessions
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: '${baseName}-cosmos'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      { locationName: location, failoverPriority: 0, isZoneRedundant: false }
    ]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    capabilities: [ { name: 'EnableServerless' } ]
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'mdr'
  properties: { resource: { id: 'mdr' } }
}

resource arrangementsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: 'arrangements'
  properties: {
    resource: {
      id: 'arrangements'
      partitionKey: { paths: [ '/id' ], kind: 'Hash' }
    }
  }
}

resource sessionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: 'sessions'
  properties: {
    resource: {
      id: 'sessions'
      partitionKey: { paths: [ '/arrangement_id' ], kind: 'Hash' }
    }
  }
}

resource caseDraftsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: 'case-drafts'
  properties: {
    resource: {
      id: 'case-drafts'
      partitionKey: { paths: [ '/id' ], kind: 'Hash' }
    }
  }
}

resource auditLogContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: 'audit-log'
  properties: {
    resource: {
      id: 'audit-log'
      partitionKey: { paths: [ '/arrangement_id' ], kind: 'Hash' }
    }
  }
}

// AI Search: optional RAG index for compliance Q&A
resource aiSearch 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${baseName}-aisearch'
  location: location
  tags: tags
  sku: { name: aiSearchSku }
  properties: {
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
  }
}

// Azure AI: OpenAI + Document Intelligence
resource openAi 'Microsoft.CognitiveServices/accounts@2024-06-01-preview' = {
  name: '${baseName}-openai'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: openAiSku }
  properties: {
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    customSubDomainName: '${baseName}-openai'
  }
}

resource openAiDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-06-01-preview' = {
  parent: openAi
  name: openAiChatDeployment
  sku: { name: 'Standard', capacity: 20 }
  properties: {
    model: { format: 'OpenAI', name: openAiChatModel, version: '2024-08-06' }
  }
}

resource openAiEmbeddings 'Microsoft.CognitiveServices/accounts/deployments@2024-06-01-preview' = {
  parent: openAi
  name: openAiEmbeddingsDeployment
  sku: { name: 'Standard', capacity: 20 }
  properties: {
    model: { format: 'OpenAI', name: openAiEmbeddingsModel, version: '1' }
  }
}

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-06-01-preview' = {
  name: '${baseName}-docintel'
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: { name: 'S0' }
  properties: {
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    customSubDomainName: '${baseName}-docintel'
  }
}

// Container Apps: MDR extraction agent API
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${baseName}-cae'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: enableObservability ? {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics!.properties.customerId
        sharedKey: logAnalytics!.listKeys().primarySharedKey
      }
    } : null
  }
}

resource mdrAgent 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${baseName}-api'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${managedIdentity.id}': {} }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: provisionAcr ? [
        {
          server: acr!.properties.loginServer
          identity: managedIdentity.id
        }
      ] : []
    }
    template: {
      containers: [
        {
          name: 'mdr-agent'
          image: effectiveContainerImage
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAi.properties.endpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: openAiChatDeployment }
            { name: 'AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT', value: openAiEmbeddingsDeployment }
            { name: 'AZURE_DOC_INTEL_ENDPOINT', value: documentIntelligence.properties.endpoint }
            { name: 'AZURE_BLOB_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
            { name: 'AZURE_BLOB_CONTAINER', value: documentsContainer.name }
            { name: 'AZURE_COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
            { name: 'AZURE_COSMOS_DATABASE', value: cosmosDb.name }
            { name: 'AZURE_COSMOS_ARRANGEMENTS_CONTAINER', value: arrangementsContainer.name }
            { name: 'AZURE_COSMOS_SESSIONS_CONTAINER', value: sessionsContainer.name }
            { name: 'AZURE_COSMOS_CASE_DRAFTS_CONTAINER', value: caseDraftsContainer.name }
            { name: 'AZURE_COSMOS_AUDIT_CONTAINER', value: auditLogContainer.name }
            { name: 'AZURE_AI_SEARCH_ENDPOINT', value: 'https://${aiSearch.name}.search.windows.net' }
            { name: 'AZURE_AI_SEARCH_INDEX_NAME', value: 'compliance-knowledge-base' }
            { name: 'AZURE_AI_SEARCH_VECTOR_FIELD', value: 'contentVector' }
            { name: 'AZURE_AI_SEARCH_SEMANTIC_CONFIGURATION', value: 'default' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: enableObservability ? appInsights!.properties.ConnectionString : '' }
            { name: 'AZURE_CLIENT_ID', value: managedIdentity.properties.clientId }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

// API Management
resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: '${baseName}-apim'
  location: location
  tags: tags
  sku: { name: 'Developer', capacity: 1 }
  properties: {
    publisherName: 'EY Tax MDR'
    publisherEmail: empty(operationsEmail) ? 'opsteam@example.com' : operationsEmail
  }
  identity: { type: 'SystemAssigned' }
}

resource apimBackend 'Microsoft.ApiManagement/service/backends@2023-05-01-preview' = {
  parent: apim
  name: 'mdr-agent-backend'
  properties: {
    protocol: 'http'
    url: 'https://${mdrAgent.properties.configuration.ingress.fqdn}'
    title: 'MDR Agent Container App'
    description: 'Container Apps backend for the MDR support API'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

resource apimApi 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = {
  parent: apim
  name: 'mdr-support-api'
  properties: {
    displayName: 'MDR Support API'
    description: 'Gateway facade for the MDR support two-agent runtime.'
    path: 'mdr'
    protocols: [
      'https'
    ]
    apiType: 'http'
    serviceUrl: 'https://${mdrAgent.properties.configuration.ingress.fqdn}'
    subscriptionRequired: false
  }
}

resource apimHealthOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: apimApi
  name: 'get-health'
  properties: {
    displayName: 'Health probe'
    method: 'GET'
    urlTemplate: '/health'
    responses: [
      {
        statusCode: 200
        description: 'Healthy'
      }
    ]
  }
}

resource apimChatOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: apimApi
  name: 'post-api-chat'
  properties: {
    displayName: 'Chat route'
    method: 'POST'
    urlTemplate: '/api/chat'
    responses: [
      {
        statusCode: 200
        description: 'Chat response'
      }
    ]
  }
}

resource apimUploadOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: apimApi
  name: 'post-api-upload'
  properties: {
    displayName: 'Upload and extract'
    method: 'POST'
    urlTemplate: '/api/upload'
    responses: [
      {
        statusCode: 200
        description: 'Extraction result'
      }
    ]
  }
}

resource apimCaseFromTextOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: apimApi
  name: 'post-api-case-from-text'
  properties: {
    displayName: 'Create case from text'
    method: 'POST'
    urlTemplate: '/api/case/from-text'
    responses: [
      {
        statusCode: 200
        description: 'Text extraction result'
      }
    ]
  }
}

resource apimSessionOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: apimApi
  name: 'post-api-session'
  properties: {
    displayName: 'Create session'
    method: 'POST'
    urlTemplate: '/api/session'
    responses: [
      {
        statusCode: 200
        description: 'Session created'
      }
    ]
  }
}

resource apimCaseOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: apimApi
  name: 'get-api-case'
  properties: {
    displayName: 'Get case'
    method: 'GET'
    urlTemplate: '/api/case/{arrangementId}'
    templateParameters: [
      {
        name: 'arrangementId'
        type: 'string'
        required: true
      }
    ]
    responses: [
      {
        statusCode: 200
        description: 'Case returned'
      }
    ]
  }
}

resource apimConfirmCaseOperation 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: apimApi
  name: 'post-api-case-confirm'
  properties: {
    displayName: 'Confirm case'
    method: 'POST'
    urlTemplate: '/api/case/{arrangementId}/confirm'
    templateParameters: [
      {
        name: 'arrangementId'
        type: 'string'
        required: true
      }
    ]
    responses: [
      {
        statusCode: 200
        description: 'Case confirmed'
      }
    ]
  }
}

resource apimApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-05-01-preview' = {
  parent: apimApi
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: apimPolicyXml
  }
}

resource openAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, managedIdentity.id, 'openAiUser')
  scope: openAi
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.openAiUser
  }
}

resource docIntelRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(documentIntelligence.id, managedIdentity.id, 'cognitiveServicesUser')
  scope: documentIntelligence
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.cognitiveServicesUser
  }
}

resource blobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, managedIdentity.id, 'blobContributor')
  scope: storage
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.blobContributor
  }
}

// Cosmos DB data-plane access is granted via sqlRoleAssignments, not Microsoft.Authorization/roleAssignments.
// The account-scoped Built-in Data Contributor role is required for the MI to read/write documents.
resource cosmosDataRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, managedIdentity.id, 'cosmosDataContributor')
  properties: {
    principalId: managedIdentity.properties.principalId
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    scope: cosmos.id
  }
}

resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, 'keyVaultSecretsUser')
  scope: keyVault
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.keyVaultSecretsUser
  }
}

resource aiSearchRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiSearch.id, managedIdentity.id, 'searchIndexReader')
  scope: aiSearch
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.searchIndexReader
  }
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (provisionAcr) {
  name: guid(resourceGroup().id, managedIdentity.id, 'acrPull')
  scope: acr
  properties: {
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionIds.acrPull
  }
}

output managedIdentityClientId string = managedIdentity.properties.clientId
output containerRegistryLoginServer string = provisionAcr ? acr!.properties.loginServer : ''
output containerRegistryName string = provisionAcr ? acr!.name : ''
output keyVaultUri string = keyVault.properties.vaultUri
output storageAccountName string = storage.name
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output openAiEndpoint string = openAi.properties.endpoint
output documentIntelligenceEndpoint string = documentIntelligence.properties.endpoint
output aiSearchEndpoint string = 'https://${aiSearch.name}.search.windows.net'
output containerAppFqdn string = mdrAgent.properties.configuration.ingress.fqdn
output apimGatewayUrl string = apim.properties.gatewayUrl
output appInsightsConnectionString string = enableObservability ? appInsights!.properties.ConnectionString : ''
