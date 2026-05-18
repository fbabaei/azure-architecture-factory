// Azure SQL Database module — AAD-only authentication.
//
// Use when a project's BRD specifies relational persistence (sessions,
// drafts, audit log, etc.). Pair with idempotent DDL under
// `infra/sql/*.sql` (see `factory-templates/sql/`).
//
// Notes:
//   * SQL authentication is disabled (`administrators` block only).
//   * No `administratorLogin` / `administratorLoginPassword` parameters.
//     The configured AAD principal is the only path in.
//   * Public network access defaults off; flip on per environment when
//     a private endpoint is not yet wired.

@description('Azure region for the SQL server and database.')
param location string

@description('Logical SQL server name (3-63 chars, lowercase, globally unique).')
@minLength(3)
@maxLength(63)
param serverName string

@description('Database name on the server.')
param databaseName string

@description('Object ID (GUID) of the AAD principal that becomes the SQL admin (user, group, or managed identity).')
param aadAdminObjectId string

@description('Display name of the AAD admin principal (user@tenant or group/MI name).')
param aadAdminLogin string

@description('Tenant ID for the AAD admin principal.')
param aadAdminTenantId string = subscription().tenantId

@description('Principal type for the AAD admin: User, Group, or Application (managed identities use Application).')
@allowed([
  'User'
  'Group'
  'Application'
])
param aadAdminPrincipalType string = 'Group'

@description('Database SKU. Defaults to General Purpose Serverless 1 vCore.')
param skuName string = 'GP_S_Gen5_1'

@description('Database tier. Must align with skuName.')
param skuTier string = 'GeneralPurpose'

@description('Maximum database size in bytes. Defaults to 32 GB.')
param maxSizeBytes int = 34359738368

@description('Auto-pause delay in minutes for serverless DBs. Use -1 to disable.')
param autoPauseDelay int = 60

@description('Allow public network access. Set false when a private endpoint is in place.')
param publicNetworkAccess bool = false

@description('Allow Azure services (e.g., App Service, Container Apps) to connect when public network access is enabled.')
param allowAzureServices bool = true

@description('Resource tags.')
param tags object = {}

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: serverName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: publicNetworkAccess ? 'Enabled' : 'Disabled'
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: aadAdminLogin
      sid: aadAdminObjectId
      tenantId: aadAdminTenantId
      principalType: aadAdminPrincipalType
    }
  }
}

resource aadOnly 'Microsoft.Sql/servers/azureADOnlyAuthentications@2023-08-01-preview' = {
  parent: sqlServer
  name: 'Default'
  properties: {
    azureADOnlyAuthentication: true
  }
}

resource allowAzure 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = if (publicNetworkAccess && allowAzureServices) {
  parent: sqlServer
  name: 'AllowAllWindowsAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    maxSizeBytes: maxSizeBytes
    autoPauseDelay: autoPauseDelay
    zoneRedundant: false
  }
  dependsOn: [
    aadOnly
  ]
}

@description('Fully qualified server name (use in connection strings).')
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName

@description('Database name.')
output sqlDatabaseName string = sqlDatabase.name

@description('AAD-auth ADO.NET connection string (no secrets). Caller supplies the identity at runtime via DefaultAzureCredential.')
output sqlConnectionStringAadDefault string = 'Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Database=${sqlDatabase.name};Authentication=Active Directory Default;Encrypt=True;TrustServerCertificate=False;'

@description('Resource ID of the SQL server.')
output sqlServerId string = sqlServer.id

@description('Resource ID of the SQL database.')
output sqlDatabaseId string = sqlDatabase.id
