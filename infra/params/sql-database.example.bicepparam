// Example parameter file for infra/modules/data/sql-database.bicep.
// Copy into a project's infra/params/ folder and edit per environment.

using '../modules/data/sql-database.bicep'

param location = 'eastus2'
param serverName = 'sql-myproject-dev'
param databaseName = 'app'

// Replace with the AAD group / managed identity that owns this database.
param aadAdminObjectId = '00000000-0000-0000-0000-000000000000'
param aadAdminLogin = 'sql-admins@contoso.com'
param aadAdminPrincipalType = 'Group'

// Serverless GP, auto-pause after 60 minutes (good for dev).
param skuName = 'GP_S_Gen5_1'
param skuTier = 'GeneralPurpose'
param autoPauseDelay = 60

// Default to private network. Flip to true only if no PE is wired.
param publicNetworkAccess = false
param allowAzureServices = true

param tags = {
  project: 'myproject'
  environment: 'dev'
  managedBy: 'azure-architecture-factory'
}
