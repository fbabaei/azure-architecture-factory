using '../main.bicep'

param baseName = 'casewright'
param environmentName = 'dev'
// Container images — override with your ACR-pushed tags after the first build.
param apiImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param workerImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
// Microsoft Graph (SharePoint) app registration — fill in for live SharePoint sync.
param graphTenantId = ''
param graphClientId = ''
param sharePointSyncSchedule = '0 0 */6 * * *'
param syncDefaultTenantId = ''
param embeddingDimensions = 3072
