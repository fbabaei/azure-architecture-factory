using '../main.bicep'

param environment = 'prod'
param workloadName = 'daop'
param foundryModelDeployment = 'gpt-4o'
param foundryEmbeddingsDeployment = 'text-embedding-3-small'
param imageTag = 'latest'
param orchestratorMinReplicas = 2
param subAgentMinReplicas = 1
param cosmosThroughput = 4000
param serviceBusSku = 'Premium'
param aafApiBaseUrl = ''
