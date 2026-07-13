// Architecture Factory — Sandbox (Phase 1)
// Subscription-scoped: creates a dedicated sandbox resource group, then deploys
// the sandbox execution resources into it. Authoring-only — provisioning is a
// gated, explicit step (see infra/sandbox/README.md).

targetScope = 'subscription'

@description('Azure region for the sandbox resources.')
param location string = 'eastus'

@description('Name of the dedicated sandbox resource group.')
param sandboxResourceGroupName string = 'arch-factory-sandbox-rg'

@description('Monthly budget (USD) for the sandbox resource group. Alert-based; hard stop is enforced by the TTL cleanup automation.')
param monthlyBudgetUsd int = 200

@description('First day of the current month, e.g. 2026-07-01. Azure budgets require the start date to be the first of a month.')
param budgetStartDate string

@description('Email addresses that receive sandbox budget alerts.')
param budgetAlertEmails array

@description('Allowed Azure regions for anything deployed into the sandbox.')
param allowedLocations array = [
  'eastus'
  'eastus2'
  'westus2'
]

@description('Container image for the ephemeral generation/execution job.')
param jobImage string = 'archfactorydevacr.azurecr.io/sandbox-runner:latest'

@description('ACR login server used by the execution job.')
param acrLoginServer string = 'archfactorydevacr.azurecr.io'

@description('Wall-clock timeout (seconds) for a single generation run.')
param jobReplicaTimeoutSeconds int = 3600

var tags = {
  workload: 'architecture-factory'
  environment: 'sandbox'
  managedBy: 'bicep'
}

resource sandboxRg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: sandboxResourceGroupName
  location: location
  tags: tags
}

module sandbox 'sandbox-resources.bicep' = {
  name: 'sandbox-resources'
  scope: sandboxRg
  params: {
    location: location
    tags: tags
    monthlyBudgetUsd: monthlyBudgetUsd
    budgetStartDate: budgetStartDate
    budgetAlertEmails: budgetAlertEmails
    allowedLocations: allowedLocations
    jobImage: jobImage
    acrLoginServer: acrLoginServer
    jobReplicaTimeoutSeconds: jobReplicaTimeoutSeconds
  }
}

output sandboxResourceGroup string = sandboxRg.name
output executionIdentityClientId string = sandbox.outputs.identityClientId
output executionIdentityPrincipalId string = sandbox.outputs.identityPrincipalId
output executionJobName string = sandbox.outputs.jobName
