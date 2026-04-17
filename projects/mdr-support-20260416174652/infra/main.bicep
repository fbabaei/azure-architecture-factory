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

@description('Azure OpenAI chat deployment name (e.g. gpt-4o)')
param openAiChatDeployment string = 'gpt-4o'

@description('Azure OpenAI chat model name')
param openAiChatModel string = 'gpt-4o'

@description('Container image for the MDR agent API')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'


var baseName = toLower(replace('${workloadName}-${environment}', '_', '-'))
var storageName = take('stg${uniqueString(resourceGroup().id, baseName)}', 24)
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
    }
    template: {
      containers: [
        {
          name: 'mdr-agent'
          image: containerImage
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAi.properties.endpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: openAiChatDeployment }
            { name: 'AZURE_DOC_INTEL_ENDPOINT', value: documentIntelligence.properties.endpoint }
            { name: 'AZURE_BLOB_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
            { name: 'AZURE_BLOB_CONTAINER', value: documentsContainer.name }
            { name: 'AZURE_COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
            { name: 'AZURE_COSMOS_DATABASE', value: cosmosDb.name }
            { name: 'AZURE_COSMOS_ARRANGEMENTS_CONTAINER', value: arrangementsContainer.name }
            { name: 'AZURE_COSMOS_SESSIONS_CONTAINER', value: sessionsContainer.name }
            { name: 'AZURE_AI_SEARCH_ENDPOINT', value: 'https://${aiSearch.name}.search.windows.net' }
            { name: 'AZURE_AI_SEARCH_INDEX_NAME', value: 'compliance-knowledge-base' }
            { name: 'AZURE_AI_SEARCH_API_KEY', value: aiSearch.listAdminKeys().primaryKey }
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

output managedIdentityClientId string = managedIdentity.properties.clientId
output keyVaultUri string = keyVault.properties.vaultUri
output storageAccountName string = storage.name
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output openAiEndpoint string = openAi.properties.endpoint
output documentIntelligenceEndpoint string = documentIntelligence.properties.endpoint
output aiSearchEndpoint string = 'https://${aiSearch.name}.search.windows.net'
output containerAppFqdn string = mdrAgent.properties.configuration.ingress.fqdn
output apimGatewayUrl string = apim.properties.gatewayUrl
output appInsightsConnectionString string = enableObservability ? appInsights!.properties.ConnectionString : ''
