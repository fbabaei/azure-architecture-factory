// Parameter file for portal + MCP server — production environment
using '../main-portal-mcp.bicep'

param environment = 'prod'
param location = 'eastus'
param projectName = 'arch-factory'
param portalImageUri = 'archfactorydevacr.azurecr.io/portal:latest'
param mcpServerImageUri = 'archfactorydevacr.azurecr.io/mcp-orchestrator:latest'
param drawioImageUri = 'archfactorydevacr.azurecr.io/drawio-mcp:latest'
param portalApiKey = ''
