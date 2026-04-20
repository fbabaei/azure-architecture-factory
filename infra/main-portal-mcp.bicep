// Azure Architecture Factory — Portal & MCP Server Deployment
// Deploys: ACR, Container Apps Environment, Portal Container App, MCP Server Container App
// Reuses existing modules for identity, Key Vault, monitoring

targetScope = 'resourceGroup'

// ── Parameters ──────────────────────────────────────────────
param environment string = 'dev'
param location string = resourceGroup().location
param projectName string = 'arch-factory'

@description('Portal container image URI (set after first ACR push)')
param portalImageUri string = ''

@description('MCP server container image URI (set after first ACR push)')
param mcpServerImageUri string = ''

@description('Draw.io MCP container image URI (set after first ACR push)')
param drawioImageUri string = ''

@description('Optional: pre-shared API key stored in Key Vault for portal mutations')
@secure()
param portalApiKey string = ''

@description('Entra ID tenant ID for OAuth 2.0 auth on mutation endpoints')
param entraTenantId string = ''

@description('Entra ID application (client) ID for the portal app registration')
param entraClientId string = ''

@description('Email addresses to notify on portal alerts. Leave empty to skip.')
param alertEmails array = []

@description('Disable the portal alert rules (useful for dev toggling). Alerts still deploy.')
param alertsEnabled bool = true

// ── Derived names ───────────────────────────────────────────
var baseName = '${projectName}-${environment}'
var acrName = replace('${baseName}acr', '-', '')
var containerEnvName = '${baseName}-env'
var portalAppName = '${baseName}-portal'
var mcpServerAppName = '${baseName}-mcp'
var drawioAppName = '${baseName}-drawio'
var identityName = '${baseName}-identity'
var keyVaultName = substring('${replace(baseName, '-', '')}kv', 0, min(24, length('${replace(baseName, '-', '')}kv')))
var appInsightsName = '${baseName}-appinsights'
var logAnalyticsName = '${baseName}-logs'

var commonTags = {
  environment: environment
  project: projectName
  stack: 'portal-mcp'
}

// Placeholder image when ACR images aren't pushed yet
var defaultImage = 'mcr.microsoft.com/k8se/quickstart:latest'
var resolvedPortalImage = !empty(portalImageUri) ? portalImageUri : defaultImage
var resolvedMcpImage = !empty(mcpServerImageUri) ? mcpServerImageUri : defaultImage
var resolvedDrawioImage = !empty(drawioImageUri) ? drawioImageUri : defaultImage

// ── Managed Identity ────────────────────────────────────────
module identity 'modules/security/managed-identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    identityName: identityName
    tags: commonTags
  }
}

// ── Key Vault ───────────────────────────────────────────────
module keyVault 'modules/security/keyvault.bicep' = {
  name: 'keyVault'
  params: {
    location: location
    keyVaultName: keyVaultName
    tenantId: subscription().tenantId
    principalId: identity.outputs.principalId
    tags: commonTags
  }
}

// Store portal API key as a secret (if provided)
resource portalApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(portalApiKey)) {
  name: '${keyVaultName}/portal-api-key'
  properties: {
    value: portalApiKey
  }
  dependsOn: [keyVault]
}

// ── Log Analytics ───────────────────────────────────────────
module logAnalytics 'modules/monitoring/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    location: location
    workspaceName: logAnalyticsName
    tags: commonTags
  }
}

// ── Application Insights ────────────────────────────────────
module appInsights 'modules/monitoring/appinsights.bicep' = {
  name: 'appInsights'
  params: {
    location: location
    appInsightsName: appInsightsName
    workspaceId: logAnalytics.outputs.workspaceId
    tags: commonTags
  }
}

// ── Container Registry ──────────────────────────────────────
module acr 'modules/compute/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    registryName: acrName
    sku: environment == 'prod' ? 'Standard' : 'Basic'
    pullPrincipalId: identity.outputs.principalId
    tags: commonTags
  }
}

// ── Container Apps Environment ──────────────────────────────
// Reference the Log Analytics workspace directly for listKeys (BCP181)
resource logAnalyticsRef 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsName
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-02-preview' = {
  name: containerEnvName
  location: location
  tags: commonTags
  dependsOn: [logAnalytics]
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsRef.properties.customerId
        sharedKey: logAnalyticsRef.listKeys().primarySharedKey
      }
    }
  }
}

// ── Portal Container App ────────────────────────────────────
module portal 'modules/compute/containerapp.bicep' = {
  name: 'portal'
  params: {
    location: location
    containerAppName: portalAppName
    containerEnvId: containerAppEnv.id
    containerImageUri: resolvedPortalImage
    containerPort: 5501
    managedIdentityId: identity.outputs.id
    environment: environment
    externalIngress: true
    cpu: '0.25'
    memory: '0.5Gi'
    minReplicas: environment == 'prod' ? 1 : 0
    maxReplicas: environment == 'prod' ? 5 : 2
    tags: commonTags
    envVars: concat([
      { name: 'ENVIRONMENT', value: environment }
      { name: 'FACTORY_PORTAL_ALLOWED_ORIGIN', value: '*' }
      { name: 'FACTORY_PORTAL_BIND', value: '0.0.0.0' }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.outputs.connectionString }
      { name: 'ENTRA_TENANT_ID', value: entraTenantId }
      { name: 'ENTRA_CLIENT_ID', value: entraClientId }
    ], !empty(portalApiKey) ? [
      { name: 'FACTORY_PORTAL_API_KEY', secretRef: 'portal-api-key' }
    ] : [])
    secrets: !empty(portalApiKey) ? [
      { name: 'portal-api-key', value: portalApiKey }
    ] : []
    registries: [
      {
        server: acr.outputs.loginServer
        identity: identity.outputs.id
      }
    ]
  }
}

// ── Draw.io MCP Container App ──────────────────────────────
module drawio 'modules/compute/containerapp.bicep' = {
  name: 'drawio'
  params: {
    location: location
    containerAppName: drawioAppName
    containerEnvId: containerAppEnv.id
    containerImageUri: resolvedDrawioImage
    containerPort: 8080
    managedIdentityId: identity.outputs.id
    environment: environment
    externalIngress: true
    cpu: '0.5'
    memory: '1Gi'
    minReplicas: environment == 'prod' ? 1 : 0
    maxReplicas: environment == 'prod' ? 3 : 2
    tags: commonTags
    envVars: [
      { name: 'PORT', value: '8080' }
      { name: 'NODE_ENV', value: 'production' }
    ]
    secrets: []
    registries: [
      {
        server: acr.outputs.loginServer
        identity: identity.outputs.id
      }
    ]
  }
}

// ── MCP Server Container App ────────────────────────────────
module mcpServer 'modules/compute/containerapp.bicep' = {
  name: 'mcpServer'
  params: {
    location: location
    containerAppName: mcpServerAppName
    containerEnvId: containerAppEnv.id
    containerImageUri: resolvedMcpImage
    containerPort: 8000
    managedIdentityId: identity.outputs.id
    environment: environment
    externalIngress: true
    cpu: '0.5'
    memory: '1Gi'
    minReplicas: environment == 'prod' ? 1 : 0
    maxReplicas: environment == 'prod' ? 5 : 3
    tags: commonTags
    envVars: concat([
      { name: 'ENVIRONMENT', value: environment }
      { name: 'SERVER_HOST', value: '0.0.0.0' }
      { name: 'SERVER_PORT', value: '8000' }
      { name: 'AZURE_MANAGED_MODE', value: 'true' }
      { name: 'PUBLIC_BASE_URL', value: 'https://${mcpServerAppName}.${containerAppEnv.properties.defaultDomain}' }
      { name: 'DRAWIO_PUBLIC_URL', value: 'https://${drawioAppName}.${containerAppEnv.properties.defaultDomain}/mcp' }
      { name: 'PORTAL_BASE_URL', value: 'https://${portalAppName}.${containerAppEnv.properties.defaultDomain}' }
      { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.outputs.connectionString }
    ], !empty(portalApiKey) ? [
      { name: 'PORTAL_API_KEY', secretRef: 'portal-api-key' }
    ] : [])
    secrets: !empty(portalApiKey) ? [
      { name: 'portal-api-key', value: portalApiKey }
    ] : []
    registries: [
      {
        server: acr.outputs.loginServer
        identity: identity.outputs.id
      }
    ]
  }
}

// ── Portal alerts ───────────────────────────────────────────
module portalAlerts 'modules/monitoring/alerts.bicep' = {
  name: 'portalAlerts'
  params: {
    location: location
    baseName: baseName
    workspaceId: logAnalytics.outputs.workspaceId
    containerAppName: portalAppName
    alertEmails: alertEmails
    enabled: alertsEnabled
    tags: commonTags
  }
}

// ── Outputs ─────────────────────────────────────────────────
output portalUrl string = portal.outputs.url
output drawioUrl string = drawio.outputs.url
output mcpServerUrl string = mcpServer.outputs.url
output mcpEndpoint string = '${mcpServer.outputs.url}/mcp'
output acrLoginServer string = acr.outputs.loginServer
output keyVaultUri string = keyVault.outputs.vaultUri
output appInsightsConnectionString string = appInsights.outputs.connectionString
output managedIdentityClientId string = identity.outputs.clientId
