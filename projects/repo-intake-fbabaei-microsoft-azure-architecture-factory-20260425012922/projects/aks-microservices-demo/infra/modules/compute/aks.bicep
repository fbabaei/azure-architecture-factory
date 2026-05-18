param location string
param aksClusterName string
param dnsPrefix string
param logAnalyticsWorkspaceId string
param acrName string

resource aks 'Microsoft.ContainerService/managedClusters@2023-08-01' = {
  name: aksClusterName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: dnsPrefix
    kubernetesVersion: '1.30.3'
    agentPoolProfiles: [
      {
        name: 'systemnp'
        mode: 'System'
        count: 1
        vmSize: 'Standard_D4s_v5'
        osType: 'Linux'
        type: 'VirtualMachineScaleSets'
      }
      {
        name: 'usernp'
        mode: 'User'
        count: 2
        vmSize: 'Standard_D4s_v5'
        osType: 'Linux'
        type: 'VirtualMachineScaleSets'
      }
    ]
    networkProfile: {
      networkPlugin: 'azure'
      networkPolicy: 'azure'
      loadBalancerSku: 'standard'
    }
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalyticsWorkspaceId
        }
      }
      azurepolicy: {
        enabled: true
      }
    }
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aks.id, acr.id, 'AcrPull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: aks.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output aksId string = aks.id
output aksName string = aks.name
output aksPrincipalId string = aks.identity.principalId
