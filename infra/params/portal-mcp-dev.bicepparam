// Parameter file for portal + MCP server — development environment
using '../main-portal-mcp.bicep'

param environment = 'dev'
param location = 'eastus'
param projectName = 'arch-factory'
param portalImageUri = 'archfactorydevacr.azurecr.io/portal:latest'
param mcpServerImageUri = 'archfactorydevacr.azurecr.io/mcp-orchestrator:latest'
param drawioImageUri = 'archfactorydevacr.azurecr.io/drawio-mcp:latest'
param portalApiKey = ''

// Leave alertEmails empty for dev; set to a list like ['ops@example.com']
// to enable email receivers on the portal alert rules.
param alertEmails = []
param alertsEnabled = true
