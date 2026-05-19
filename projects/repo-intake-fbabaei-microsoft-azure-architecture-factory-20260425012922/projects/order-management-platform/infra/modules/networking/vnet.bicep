metadata description = 'Virtual Network for OrderManagement Platform'

param location string
param projectName string
param environment string
param commonTags object

var vnetName = '${projectName}-vnet-${environment}-${location}'
var addressPrefix = '10.0.0.0/16'

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  tags: commonTags
  properties: {
    addressSpace: {
      addressPrefixes: [
        addressPrefix
      ]
    }
    subnets: [
      {
        name: 'compute-subnet'
        properties: {
          addressPrefix: '10.0.1.0/24'
          serviceEndpoints: [
            {
              service: 'Microsoft.Sql'
            }
            {
              service: 'Microsoft.Storage'
            }
          ]
        }
      }
      {
        name: 'data-subnet'
        properties: {
          addressPrefix: '10.0.2.0/24'
          serviceEndpoints: [
            {
              service: 'Microsoft.Sql'
            }
            {
              service: 'Microsoft.Storage'
            }
          ]
        }
      }
      {
        name: 'gateway-subnet'
        properties: {
          addressPrefix: '10.0.3.0/24'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output computeSubnetId string = '${vnet.id}/subnets/compute-subnet'
output dataSubnetId string = '${vnet.id}/subnets/data-subnet'
output gatewaySubnetId string = '${vnet.id}/subnets/gateway-subnet'
