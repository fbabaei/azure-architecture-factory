// Architecture Factory — Sandbox execution resources (Phase 1, RG-scoped)
// Deployed into the dedicated sandbox resource group by infra/sandbox/main.bicep.
//
// Provides:
//  - a least-privilege user-assigned managed identity (Contributor on THIS RG only)
//  - region allowlist + require-expiresOn-tag policy assignments
//  - a monthly cost budget (alert-based)
//  - an isolated Container Apps environment + ephemeral execution Job
//    (no host mounts, resource + wall-clock caps) that runs generation/Copilot work

@description('Azure region.')
param location string

@description('Common tags.')
param tags object = {}

@description('Monthly budget (USD).')
param monthlyBudgetUsd int

@description('Budget start date (first of a month, e.g. 2026-07-01).')
param budgetStartDate string

@description('Emails that receive budget alerts.')
param budgetAlertEmails array

@description('Allowed Azure regions for anything created in this RG.')
param allowedLocations array

@description('Execution job container image.')
param jobImage string

@description('ACR login server.')
param acrLoginServer string

@description('Wall-clock timeout (seconds) for a single run.')
param jobReplicaTimeoutSeconds int

var namePrefix = 'aaf-sandbox'
var contributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')

// --- Least-privilege identity used by the execution job -------------------
resource execIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-exec-id'
  location: location
  tags: tags
}

// Contributor on THIS resource group only (not the subscription, not prod).
resource execContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, execIdentity.id, 'contributor')
  properties: {
    roleDefinitionId: contributorRoleId
    principalId: execIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- Guardrail policies (scoped to this RG) -------------------------------
// Allowed locations (built-in policy definition).
resource allowedLocationsPolicy 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: 'sandbox-allowed-locations'
  location: location
  identity: {
    type: 'None'
  }
  properties: {
    displayName: 'Sandbox - allowed locations'
    policyDefinitionId: subscriptionResourceId('Microsoft.Authorization/policyDefinitions', 'e56962a6-4747-49cd-b67b-bf8b01975c4c')
    parameters: {
      listOfAllowedLocations: {
        value: allowedLocations
      }
    }
  }
}

// Require the expiresOn tag so the TTL cleanup can reap resources.
resource requireExpiresTag 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: 'sandbox-require-expireson'
  properties: {
    displayName: 'Sandbox - require expiresOn tag on resources'
    policyDefinitionId: subscriptionResourceId('Microsoft.Authorization/policyDefinitions', '871b6d14-10aa-478d-b590-94f262ecfa99')
    parameters: {
      tagName: {
        value: 'expiresOn'
      }
    }
  }
}

// --- Cost guardrail (alert-based; hard stop via TTL cleanup automation) ----
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: '${namePrefix}-budget'
  properties: {
    category: 'Cost'
    amount: monthlyBudgetUsd
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      actual50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: budgetAlertEmails
      }
      actual90: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 90
        thresholdType: 'Actual'
        contactEmails: budgetAlertEmails
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: budgetAlertEmails
      }
    }
  }
}

// --- Isolated execution runtime -------------------------------------------
resource logws 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logws.properties.customerId
        sharedKey: logws.listKeys().primarySharedKey
      }
    }
  }
}

// Ephemeral, manually-triggered job. No volumes/host mounts. Capped CPU/memory
// and wall-clock time. Pulls its image from ACR using the sandbox identity.
resource execJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${namePrefix}-exec-job'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${execIdentity.id}': {}
    }
  }
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: jobReplicaTimeoutSeconds
      replicaRetryLimit: 0
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: acrLoginServer
          identity: execIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'sandbox-runner'
          image: jobImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'SANDBOX_RESOURCE_GROUP'
              value: resourceGroup().name
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: execIdentity.properties.clientId
            }
          ]
        }
      ]
    }
  }
}

output identityClientId string = execIdentity.properties.clientId
output identityPrincipalId string = execIdentity.properties.principalId
output jobName string = execJob.name
output environmentId string = env.id
