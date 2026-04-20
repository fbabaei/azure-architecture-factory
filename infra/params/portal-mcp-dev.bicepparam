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
param alertEmails = ['fbabaei@microsoft.com']

// Paste a Microsoft Teams incoming-webhook URL (or Power Automate
// "When a Teams webhook request is received" URL) here to forward
// portal alerts into Teams. Leave empty to skip.
param teamsWebhookUrl = ''
param alertsEnabled = true

// CORS allowed origin(s). '*' is fine for dev; prod should pin to
// 'https://arch-factory-prod-portal.<region>.azurecontainerapps.io'.
param allowedOrigin = '*'
