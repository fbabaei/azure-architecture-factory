using '../main.bicep'

param baseName = 'casewright'
param environmentName = 'prod'
param apiImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param workerImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
param graphTenantId = ''
param graphClientId = ''
param sharePointSyncSchedule = '0 0 */6 * * *'
param syncDefaultTenantId = ''
param embeddingDimensions = 3072
