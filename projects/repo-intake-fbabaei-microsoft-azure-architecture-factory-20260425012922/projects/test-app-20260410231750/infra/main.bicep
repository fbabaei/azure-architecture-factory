targetScope = 'resourceGroup'

@description('Deployment location')
param location string = resourceGroup().location

@description('Environment name')
param environment string = 'dev'

output deploymentHint string = 'Replace this starter Bicep file with workload-specific Azure resources.'
output locationUsed string = location
output environmentName string = environment
