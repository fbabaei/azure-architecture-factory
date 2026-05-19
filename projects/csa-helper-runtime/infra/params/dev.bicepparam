using '../main.bicep'

param projectName = 'csa-helper-runtime'
param environment = 'dev'
param location = 'eastus2'

// Initial deploy uses a public hello-world image so the platform comes up
// before the runtime image is built and pushed. After Phase 5 you should
// rebuild with the actual runtime image:
//    <acr-login-server>/csa-helper-runtime:<tag>
param containerImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// EXISTING Azure OpenAI — do NOT create.
param aoaiAccountName = 'fbfoundrywestus'
param aoaiResourceGroupName = 'rg-fbabaei-2653'
param aoaiEndpoint = 'https://fbfoundrywestus.openai.azure.com/'
param aoaiDeployment = 'gpt-4o'
param aoaiApiVersion = '2024-10-21'

param minReplicas = 0
param maxReplicas = 3
