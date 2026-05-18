using '../main.bicep'

param environment = 'dev'
param workloadName = 'daop'
param foundryModelDeployment = 'gpt-4o'
param foundryEmbeddingsDeployment = 'text-embedding-3-small'
param imageTag = 'latest'
param orchestratorMinReplicas = 1
param subAgentMinReplicas = 0
param cosmosThroughput = 400
param serviceBusSku = 'Standard'
param aafApiBaseUrl = ''
