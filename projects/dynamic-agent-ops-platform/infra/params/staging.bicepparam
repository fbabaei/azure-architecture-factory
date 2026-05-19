using '../main.bicep'

param environment = 'staging'
param workloadName = 'daop'
param foundryModelDeployment = 'gpt-4o'
param foundryEmbeddingsDeployment = 'text-embedding-3-small'
param imageTag = 'latest'
param orchestratorMinReplicas = 1
param subAgentMinReplicas = 1
param cosmosThroughput = 1000
param serviceBusSku = 'Standard'
param aafApiBaseUrl = ''
