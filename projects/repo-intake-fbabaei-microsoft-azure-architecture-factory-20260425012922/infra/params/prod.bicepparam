// Parameter file for production environment
using '../main.bicep'

param environment = 'prod'
param location = 'eastus'
param projectName = 'ai-agent'
param containerImageUri = 'mycontainerregistry.azurecr.io/agent:latest'
param containerPort = 8000
