// Azure Monitor alert rules for the factory portal.
//
// Creates an Action Group (email receivers) and three scheduled-query-rules
// that fire on structured log signals emitted by the portal:
//   1. /ready probe reports degraded
//   2. Runs killed by the pipeline watchdog (returnCode=-2)
//   3. Sustained HTTP 5xx rate from the portal container
//
// Alerts run on the Log Analytics workspace attached to the Container Apps
// environment, so no extra data source is required.

targetScope = 'resourceGroup'

@description('Azure region for alert resources.')
param location string = resourceGroup().location

@description('Base name (e.g. arch-factory-dev).')
param baseName string

@description('Log Analytics workspace resource id to query.')
param workspaceId string

@description('Container app name to scope queries (e.g. arch-factory-dev-portal).')
param containerAppName string

@description('Email addresses to notify. Leave empty to skip receiver creation.')
param alertEmails array = []

@description('Alert severity (0 critical … 4 verbose). Default 2 = warning.')
@minValue(0)
@maxValue(4)
param severity int = 2

@description('Enable / disable all alert rules (useful for dev toggling).')
param enabled bool = true

@description('Tags propagated to every resource.')
param tags object = {}

var actionGroupName = '${baseName}-alerts-ag'
var shortName = substring(replace(baseName, '-', ''), 0, min(12, length(replace(baseName, '-', ''))))

// Queries are built with single-quoted interpolation so containerAppName is
// substituted (triple-quoted Bicep strings are verbatim and do NOT perform
// ${} substitution — avoid those here).
var queryReadyDegraded = 'ContainerAppConsoleLogs_CL\n| where ContainerAppName_s == "${containerAppName}"\n| where Log_s has \'"path": "/ready"\'\n| where Log_s has \'"status": "degraded"\' or Log_s has \'"status":"degraded"\''

var queryWatchdog = 'ContainerAppConsoleLogs_CL\n| where ContainerAppName_s == "${containerAppName}"\n| where Log_s has "[watchdog]" or Log_s has "returnCode=-2"'

var query5xx = 'ContainerAppConsoleLogs_CL\n| where ContainerAppName_s == "${containerAppName}"\n| where Log_s matches regex \'"status"\\\\s*:\\\\s*5\\\\d\\\\d\'\n| where Log_s !has \'"path": "/ready"\' and Log_s !has \'"path": "/health"\''

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: actionGroupName
  location: 'global'
  tags: tags
  properties: {
    groupShortName: shortName
    enabled: true
    emailReceivers: [for (email, i) in alertEmails: {
      name: 'email-${i}'
      emailAddress: email
      useCommonAlertSchema: true
    }]
  }
}

var actionsBlock = {
  actionGroups: [actionGroup.id]
}

resource alertReadyDegraded 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: '${baseName}-alert-ready-degraded'
  location: location
  tags: tags
  properties: {
    displayName: 'Portal /ready degraded'
    description: 'Fires when the portal /ready probe returns a non-ok status.'
    severity: severity
    enabled: enabled
    scopes: [workspaceId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT10M'
    criteria: {
      allOf: [
        {
          query: queryReadyDegraded
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 2
          failingPeriods: {
            minFailingPeriodsToAlert: 1
            numberOfEvaluationPeriods: 1
          }
        }
      ]
    }
    actions: actionsBlock
    autoMitigate: true
  }
}

resource alertWatchdogKills 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: '${baseName}-alert-watchdog-kills'
  location: location
  tags: tags
  properties: {
    displayName: 'Portal watchdog terminated stuck runs'
    description: 'Fires when the pipeline watchdog marks runs as failed (returnCode=-2).'
    severity: severity
    enabled: enabled
    scopes: [workspaceId]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT30M'
    criteria: {
      allOf: [
        {
          query: queryWatchdog
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 1
          failingPeriods: {
            minFailingPeriodsToAlert: 1
            numberOfEvaluationPeriods: 1
          }
        }
      ]
    }
    actions: actionsBlock
    autoMitigate: true
  }
}

resource alert5xxRate 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: '${baseName}-alert-5xx-rate'
  location: location
  tags: tags
  properties: {
    displayName: 'Portal sustained HTTP 5xx rate'
    description: 'Fires when the portal emits 5+ 5xx responses in 15 minutes (excluding /ready & /health probes).'
    severity: severity
    enabled: enabled
    scopes: [workspaceId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: query5xx
          timeAggregation: 'Count'
          operator: 'GreaterThanOrEqual'
          threshold: 5
          failingPeriods: {
            minFailingPeriodsToAlert: 1
            numberOfEvaluationPeriods: 1
          }
        }
      ]
    }
    actions: actionsBlock
    autoMitigate: true
  }
}

output actionGroupId string = actionGroup.id
output alertIds array = [
  alertReadyDegraded.id
  alertWatchdogKills.id
  alert5xxRate.id
]
