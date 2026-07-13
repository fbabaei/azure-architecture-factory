using '../main.bicep'

// Fill these in for your environment before deploying.
param location = 'eastus'
param sandboxResourceGroupName = 'arch-factory-sandbox-rg'
param monthlyBudgetUsd = 200
// Must be the first day of the current month.
param budgetStartDate = '2026-07-01'
// TODO: set the real alert recipients.
param budgetAlertEmails = [
  'admin@MngEnvMCAP688316.onmicrosoft.com'
]
param allowedLocations = [
  'eastus'
  'eastus2'
  'westus2'
]
param jobImage = 'archfactorydevacr.azurecr.io/sandbox-runner:latest'
param acrLoginServer = 'archfactorydevacr.azurecr.io'
param jobReplicaTimeoutSeconds = 3600
